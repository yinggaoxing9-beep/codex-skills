#!/usr/bin/env python3
"""Resumable WeChat account archive. Python 3.11+, standard library core."""
from __future__ import annotations
import argparse
import contextlib
import csv
import difflib
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse as up
import urllib.request as ur
import uuid

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36'
BACKEND = 'wechat-platform-raw-v1'


def dumps(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def digest(x):
    return hashlib.sha256((x if isinstance(x, bytes) else dumps(x).encode())).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
    os.replace(tmp, path)


def default_root():
    if os.name == 'nt':
        return Path.home() / 'Documents' / 'CodexData' / 'wechat-account-archive'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'wechat-account-archive'


def safe_root(path):
    p = Path(path).expanduser().resolve()
    skill = Path(__file__).resolve().parents[1]
    if p == Path.home().resolve() or p in Path.home().resolve().parents or p == skill or skill in p.parents or p in skill.parents or any((q / '.git').exists() for q in (p, *p.parents)):
        raise Problem('unsafe_data_root', '数据目录必须在 Skill 和 Git 仓库以外')
    return p


class Problem(Exception):
    def __init__(self, code, message='', details=None):
        self.code, self.message, self.details = code, message or code, details
        super().__init__(self.message)

    def record(self):
        return {'code': self.code, 'message': self.message, 'details': self.details}


def request_url(url):
    """Preserve public article query parameters; canonical URLs are for identity only."""
    url = html.unescape(url).strip()
    if any(ord(c) < 32 for c in url):
        raise Problem('restricted_url')
    p = up.urlsplit(url)
    if (p.netloc != 'mp.weixin.qq.com' or p.scheme not in ('http', 'https')
            or not (p.path == '/s' or p.path.startswith('/s/'))):
        raise Problem('restricted_url', '仅接受微信原文链接；HTTP 自动升级为 HTTPS')
    return up.urlunsplit(('https', 'mp.weixin.qq.com', p.path, p.query, ''))


def canonical(url):
    p = up.urlsplit(request_url(url))
    q = up.parse_qs(p.query)
    keys = ['__biz', 'mid', 'idx', 'sn']
    query = up.urlencode([(k, q[k][0]) for k in keys if k in q])
    return up.urlunsplit(('https', 'mp.weixin.qq.com', p.path, query, ''))


def biz(url):
    return up.parse_qs(up.urlsplit(html.unescape(url)).query).get('__biz', [''])[0]


def redact(obj):
    if isinstance(obj, dict):
        return {k: ('[redacted]' if re.search(r'cookie|token|ticket|password|secret|credential', k, re.I) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        if obj.lstrip().startswith(('{', '[')):
            try:
                return redact(json.loads(obj))
            except ValueError:
                pass
        return re.sub(r'(?i)([?&](?:token|ticket|key|pass_ticket|uin)=)[^&\s"<>]*', r'\1[redacted]', obj)
    return obj


class NoRedirect(ur.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTP:
    def __init__(self, interval=2.0, retries=2):
        self.interval, self.retries, self.last = interval, retries, 0.0
        self.opener = ur.build_opener(NoRedirect)

    def get(self, url, cookie='', limit=16_000_000):
        if up.urlsplit(url).scheme != 'https':
            raise Problem('restricted_url')
        if cookie and up.urlsplit(url).hostname != 'mp.weixin.qq.com':
            raise Problem('restricted_url')
        for attempt in range(self.retries + 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            headers = {'User-Agent': UA, 'Referer': 'https://mp.weixin.qq.com/'}
            if cookie:
                headers['Cookie'] = cookie
            try:
                with self.opener.open(ur.Request(url, headers=headers), timeout=30) as r:
                    data = r.read(limit + 1)
                    if len(data) > limit:
                        raise Problem('size_limit')
                    return data, r.headers.get('Content-Type', ''), r.geturl()
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    target = up.urlsplit(up.urljoin(url, e.headers.get('Location', '')))
                    if target.hostname == 'mp.weixin.qq.com' and target.path.startswith('/mp/wappoc_appmsgcaptcha'):
                        raise Problem('captcha_required', '微信返回验证跳转；不自动重试或绕过验证') from None
                    raise Problem('redirect_required', f'HTTP {e.code}；未自动跟随重定向') from None
                code = {401: 'login_required', 403: 'restricted', 404: 'deleted', 429: 'rate_limited'}.get(e.code, 'http_error')
                if e.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise Problem(code, f'HTTP {e.code}') from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == self.retries:
                    raise Problem('network_error', '网络请求失败；URL 和凭据不写入日志') from None
            time.sleep(min(16, 2 ** (attempt + 1)))


class Platform:
    def __init__(self, session, http):
        if not session.is_file():
            raise Problem('login_required', '请运行 login，用有公众号管理权限的微信扫码登录公众平台')
        self.credentials = json.loads(session.read_text(encoding='utf-8'))
        if not isinstance(self.credentials, dict):
            raise Problem('login_required', 'session.json 必须是凭据对象')
        if not all(self.credentials.get(k) for k in ('token', 'cookie')):
            raise Problem('login_required', 'session.json 缺少 token 或 cookie')
        self.http = http

    def api(self, endpoint, params):
        args = dict(params, token=self.credentials['token'], lang='zh_CN', f='json', ajax=1)
        raw, _, _ = self.http.get('https://mp.weixin.qq.com/cgi-bin/' + endpoint + '?' + up.urlencode(args), self.credentials['cookie'])
        try:
            obj = json.loads(raw)
        except ValueError:
            raise Problem('login_or_captcha', '接口返回非 JSON，需要检查登录或验证码') from None
        if not isinstance(obj, dict):
            raise Problem('parse_failed', '接口 JSON 不是对象')
        ret = obj.get('base_resp', {}).get('ret')
        if ret != 0:
            code = {200003: 'login_required', 200013: 'rate_limited', 200002: 'invalid_account_or_args'}.get(ret, 'platform_error')
            raise Problem(code, f'微信接口 ret={ret}；响应未作为成功处理')
        return obj

    def search_page(self, query, begin, count):
        return self.api('searchbiz', {'action': 'search_biz', 'query': query, 'begin': begin, 'count': count})

    def page(self, fakeid, begin, count):
        return self.api('appmsgpublish', {'sub': 'list', 'search_field': 'null', 'begin': begin, 'count': count,
            'query': '', 'fakeid': fakeid, 'type': '101_1', 'free_publish_type': 1, 'sub_action': 'list_ex'})


def decode_object(value, label):
    try:
        value = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        raise Problem('parse_failed', f'{label} JSON 损坏') from None
    if not isinstance(value, dict):
        raise Problem('parse_failed', f'{label} 必须是对象')
    return value


def parse_page(raw):
    if not isinstance(raw, dict):
        raise Problem('parse_failed', '目录响应必须是对象')
    if raw.get('base_resp', {}).get('ret') != 0:
        raise Problem('platform_error', '缺少成功响应标识')
    page = decode_object(raw.get('publish_page'), 'publish_page')
    batches = page.get('publish_list')
    if not isinstance(batches, list):
        raise Problem('parse_failed', '缺少 publish_list')
    total = page.get('total_count')
    if total is not None and (isinstance(total, bool) or not isinstance(total, int) or total < 0):
        raise Problem('parse_failed', 'total_count 格式错误')
    articles, signatures = [], []
    for i, batch in enumerate(batches):
        if not isinstance(batch, dict):
            raise Problem('parse_failed', f'推送 {i} 格式错误')
        info = decode_object(batch.get('publish_info'), f'publish_info[{i}]')
        items = info.get('appmsgex')
        if not isinstance(items, list) or not items:
            raise Problem('parse_failed', f'推送 {i} 缺少非空 appmsgex；禁止静默跳过')
        current = []
        for j, item in enumerate(items):
            if not isinstance(item, dict) or not item.get('link') or not item.get('title'):
                raise Problem('parse_failed', f'推送 {i} 文章 {j} 缺少标题/URL')
            a = dict(item)
            a['canonical_url'] = canonical(a['link'])
            a['source_id'] = str(a.get('aid') or a['canonical_url'])
            a['metadata_hash'] = digest({k: a.get(k) for k in ('source_id', 'title', 'canonical_url', 'create_time', 'update_time', 'author', 'digest', 'cover')})
            current.append((a['source_id'], a['metadata_hash']))
            articles.append(a)
        signatures.append(digest(current))
    return signatures, articles, total


class Content(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.parts, self.images, self.meta = [], [], [], {}
        self.body_depth = None
        self.capture = None
        self.skip = 0
        self.unsupported = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        void = tag in ('img', 'br', 'hr', 'meta', 'link', 'input', 'source', 'wbr', 'area', 'embed')
        if a.get('id') == 'js_content':
            self.body_depth = len(self.stack)
        field = {'activity-name': 'title', 'js_name': 'nickname', 'js_author_name': 'author'}.get(a.get('id'))
        if field:
            self.capture = (field, len(self.stack))
        if tag == 'meta' and a.get('property') in ('og:title', 'og:description'):
            self.meta[a['property']] = a.get('content', '')
        if self.body_depth is not None:
            if tag in ('script', 'style'):
                self.skip += 1
            if tag in ('p', 'section', 'div', 'br', 'h1', 'h2', 'h3', 'li'):
                self.parts.append('\n')
            if tag in ('video', 'audio', 'iframe', 'mpvoice', 'mpvideo'):
                self.unsupported.append({'kind': tag, 'status': 'unsupported', 'url': a.get('src', a.get('data-src', ''))})
            if tag == 'img':
                src = a.get('data-src') or a.get('src')
                if src:
                    src = up.urljoin('https://mp.weixin.qq.com/', html.unescape(src))
                    self.images.append(src)
                    self.parts.append(f'\n![image {len(self.images)}](ASSET_{len(self.images)})\n')
        if not void:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag not in self.stack:
            return
        pos = len(self.stack) - 1 - self.stack[::-1].index(tag)
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1
        if self.capture and pos <= self.capture[1]:
            self.capture = None
        if self.body_depth is not None and pos <= self.body_depth:
            self.body_depth = None
        del self.stack[pos:]

    def handle_data(self, data):
        if self.capture:
            field = self.capture[0]
            self.meta[field] = self.meta.get(field, '') + data
        if self.body_depth is not None and not self.skip:
            self.parts.append(data)


def parse_content(raw):
    source = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw
    if re.search(r'\b(?:is_pay_subscribe|is_pay)\s*=\s*[\"\']?1\b', source):
        raise Problem('restricted', '付费内容需要已授权的访问；不把试读当完整正文')
    p = Content()
    p.feed(source)
    text = re.sub(r'\n[ \t]*\n+', '\n\n', ''.join(p.parts)).strip()
    if not text and not p.images:
        for code, pattern in [('captcha_required', r'wappoc_appmsgcaptcha|环境异常|完成验证|验证码'),
                              ('rate_limited', r'操作频繁|访问过于频繁'), ('deleted', r'该内容已被发布者删除|内容已删除|此内容因违规无法查看'),
                              ('restricted', r'付费阅读|登录后阅读|无权查看|内容暂时无法查看')]:
            if re.search(pattern, source):
                raise Problem(code)
        raise Problem('parse_failed', '未获取非空正文或图片；HTTP 200 不代表成功')
    out = {k: v.strip() for k, v in p.meta.items()}
    out.update(text=text, images=p.images, unsupported=p.unsupported)
    for key, pattern in [('biz', r'\b(?:var\s+)?biz\s*=\s*["\x27]([^"\x27]+)'),
                         ('published_at', r'\b(?:var\s+)?ct\s*=\s*["\x27]?(\d{9,})'),
                         ('original', r'\b(?:var\s+)?isOriginal\s*=\s*["\x27]?(\d)')]:
        m = re.search(pattern, source)
        out[key] = html.unescape(m.group(1)) if m else None
    out['title'] = out.get('title') or out.get('og:title', '')
    return out


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'archive.sqlite')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS articles (
          id TEXT PRIMARY KEY, canonical TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', detail TEXT, content TEXT,
          fetched REAL, first_seen REAL NOT NULL, last_seen REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS assets (url TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence (
          id INTEGER PRIMARY KEY, run TEXT, pass INTEGER, begin INTEGER, kind TEXT,
          fetched REAL, response TEXT NOT NULL);
        ''')
        columns = {r[1] for r in self.db.execute('PRAGMA table_info(articles)')}
        if 'attempted' not in columns:
            self.db.execute('ALTER TABLE articles ADD COLUMN attempted REAL')
        self.db.commit()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, dumps(value)))

    def evidence(self, run, begin, kind, raw):
        self.db.execute('INSERT INTO evidence(run,pass,begin,kind,fetched,response) VALUES (?,?,?,?,?,?)',
            (run['id'], run['pass'], begin, kind, time.time(), dumps(redact(raw))))
        self.db.commit()

    def ingest(self, articles):
        for a in articles:
            now = time.time()
            existing = self.db.execute('SELECT * FROM articles WHERE canonical=? OR id=?', (a['canonical_url'], digest(a['source_id'])[:24])).fetchone()
            ident = existing['id'] if existing else digest(a['source_id'])[:24]
            if existing:
                old = json.loads(existing['payload'])
                a['observed_urls'] = sorted(set(old.get('observed_urls', [old['link']]) + [a['link']]))
                changed = old['metadata_hash'] != a['metadata_hash']
                self.db.execute('UPDATE articles SET payload=?,status=?,last_seen=? WHERE id=?',
                    (dumps(a), 'pending' if changed else existing['status'], now, ident))
            else:
                a['observed_urls'] = [a['link']]
                self.db.execute('INSERT INTO articles(id,canonical,payload,first_seen,last_seen) VALUES(?,?,?,?,?)',
                    (ident, a['canonical_url'], dumps(a), now, now))

    def close(self):
        self.db.close()


def new_run():
    return {'id': uuid.uuid4().hex, 'cutoff': time.time(), 'pass': 0, 'begin': 0, 'batches': [],
            'passes': [], 'totals': [], 'pages': 0, 'empty_checks': 0, 'status': 'running', 'problem': None}


def enumerate_history(store, backend, fakeid, max_pages=10000, page_size=10, max_passes=4):
    """Checkpoint before cursor advance. Repeat whole passes to detect offset drift."""
    run = store.get('run')
    if not run or run['status'] == 'stable':
        run = new_run()
    run['status'], run['problem'] = 'running', None
    store.put('run', run)
    store.db.commit()
    calls = 0
    def fetch(begin, count):
        nonlocal calls
        if calls >= max_pages:
            raise Problem('page_budget', '达到请求预算；保留当前页检查点，续跑建议预算至少为 3')
        calls += 1
        return backend.page(fakeid, begin, count)
    try:
        while calls < max_pages:
            begin = run['begin']
            raw = fetch(begin, page_size)
            store.evidence(run, begin, 'page', raw)
            signatures, articles, total = parse_page(raw)
            if len(signatures) > page_size:
                raise Problem('pagination_contract', '返回推送数超过请求数')
            if total is not None:
                run['totals'].append(total)
            if signatures:
                if begin:
                    probe = fetch(begin - 1, 2)
                    store.evidence(run, begin - 1, 'overlap', probe)
                    prev, _, _ = parse_page(probe)
                    if prev != [run['batches'][-1], signatures[0]]:
                        code = 'offset_drift' if len(prev) == 2 else 'repeated_page'
                        raise Problem(code, '重叠页不匹配；需检查偏移或重复页')
                if len(signatures) != len(set(signatures)) or any(s in run['batches'] for s in signatures):
                    raise Problem('repeated_page', '推送重复或游标不前进')
                for article in articles:
                    article['catalog_run'], article['catalog_pass'] = run['id'], run['pass']
                with store.db:
                    store.ingest(articles)
                    run['batches'].extend(signatures)
                    run['begin'] += len(signatures)  # publish batches, NEVER expanded article count
                    run['pages'] += 1
                    run['empty_checks'] = 0
                    store.put('run', run)
                continue
            if total is not None and total > begin:
                run.setdefault('warnings', []).append({'code': 'total_unit_or_empty_anomaly', 'begin': begin, 'reported_total': total})
            run['empty_checks'] += 1
            if run['empty_checks'] < 2:
                store.put('run', run)
                store.db.commit()
                continue
            tail = fetch(begin + 1, 1)
            store.evidence(run, begin + 1, 'tail_probe', tail)
            if parse_page(tail)[0]:
                raise Problem('unexpected_empty', '空页之后仍有推送')
            finished = {'batches': run['batches'], 'end': begin, 'totals': sorted(set(run['totals'])), 'tail_checks': 3}
            run['passes'].append(finished)
            if len(run['passes']) >= 2 and run['passes'][-2] == finished:
                run['status'] = 'stable'
                run['finished_at'] = time.time()
                store.put('run', run)
                store.db.commit()
                return run
            if len(run['passes']) >= max_passes:
                run['pass'] += 1
                run.update(begin=0, batches=[], totals=[], empty_checks=0)
                raise Problem('unstable_history', '达到复核轮数上限，目录仍不稳定；下次开始新的复核轮')
            run['pass'] += 1
            run.update(begin=0, batches=[], totals=[], empty_checks=0)
            store.put('run', run)
            store.db.commit()
        raise Problem('page_budget', '达到本次请求预算；下次从检查点继续')
    except Problem as e:
        run['status'], run['problem'] = 'partial', e.record()
        if e.code == 'offset_drift':
            run['pass'] += 1
            run.update(begin=0, batches=[], totals=[], empty_checks=0)
        store.put('run', run)
        store.db.commit()
        return run


def discover(backend, name, root):
    candidates = {}
    queries = [name]
    if len(name) >= 4:
        queries += [name[:len(name)//2], name[-(len(name)//2):]]
    evidence = []
    for query in dict.fromkeys(queries):
        for begin in range(0, 100, 5):
            raw = backend.search_page(query, begin, 5)
            evidence.append({'query': query, 'begin': begin, 'response': redact(raw)})
            rows = raw.get('list')
            if not isinstance(rows, list):
                raise Problem('parse_failed', '搜索缺少 list')
            for a in rows:
                if not isinstance(a, dict) or not a.get('fakeid'):
                    raise Problem('parse_failed', '搜索候选缺少 fakeid')
                candidates[a['fakeid']] = a
            if len(rows) < 5:
                break
        else:
            atomic(root / 'search.json', dumps(evidence))
            raise Problem('search_incomplete', '候选搜索达到上限，不能排除重名')
        if candidates and any(a.get('nickname') == name for a in candidates.values()):
            break
    atomic(root / 'search.json', dumps(evidence))
    return list(candidates.values())


def resolve_account(backend, name, root, http, selected=None, sample=None):
    cache_path = root / 'identities.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    old = cache.get(name)
    candidates = discover(backend, old['nickname'] if old else name, root)
    ranked = sorted(candidates, key=lambda a: difflib.SequenceMatcher(None, name, a.get('nickname', '')).ratio(), reverse=True)
    exact = [a for a in ranked if a.get('nickname') == name]
    if selected:
        chosen = [a for a in candidates if a['fakeid'] == selected]
    elif old:
        chosen = [a for a in candidates if a['fakeid'] == old['fakeid'] and a.get('alias') == old.get('alias')]
    elif len(exact) == 1:
        chosen = exact
    else:
        close = [a for a in ranked if difflib.SequenceMatcher(None, name, a.get('nickname', '')).ratio() >= .8]
        chosen = close if len(close) == 1 else []
    if len(chosen) != 1:
        raise Problem('identity_ambiguous', '需核对候选名称、alias、简介后选择；禁止仅凭近似名称绑定',
                      [{k: a.get(k) for k in ('nickname', 'fakeid', 'alias', 'signature')} for a in ranked[:12]])
    a = chosen[0]
    raw = backend.page(a['fakeid'], 0, 1)
    atomic(root / 'identity-page.json', dumps(redact(raw)))
    _, items, _ = parse_page(raw)
    if not items:
        raise Problem('identity_unverified', '候选没有可读取文章，无法独立核验账号')
    identity_failures = []
    for item in items[:5]:
        try:
            content_raw, _, _ = http.get(request_url(item['link']))
            content = parse_content(content_raw)
            chosen_item = item
            break
        except Problem as e:
            identity_failures.append(e.record())
    else:
        raise Problem('identity_unverified', '候选文章尚不能独立读取核验', identity_failures)
    evidence = {'nickname': content.get('nickname'), 'author': content.get('author'), 'biz': content.get('biz'),
                'article_url': chosen_item['canonical_url'], 'checked_at': time.time()}
    if content.get('nickname') != a.get('nickname'):
        raise Problem('identity_unverified', '文章页账号名称与搜索候选不一致', evidence)
    account_biz = biz(chosen_item['link']) or content.get('biz')
    if not account_biz or (content.get('biz') and account_biz != content['biz']):
        raise Problem('identity_unverified', '缺少一致的微信 biz 身份证据', evidence)
    if old and not selected and (old.get('backend') != BACKEND or old.get('biz') != account_biz or old['fakeid'] != a['fakeid']):
        raise Problem('identity_changed', '已缓存映射与当前身份不一致，必须重新核验', evidence)
    if sample:
        sample_raw, _, _ = http.get(request_url(sample))
        sample_content = parse_content(sample_raw)
        if sample_content.get('biz') != account_biz or sample_content.get('nickname') != a['nickname']:
            raise Problem('sample_mismatch', '可选样本与候选账号身份不一致')
        evidence['sample_verified'] = canonical(sample)
    mapping = {k: a.get(k) for k in ('fakeid', 'nickname', 'alias', 'signature')}
    mapping.update(backend=BACKEND, biz=account_biz, evidence=evidence, verified_at=time.time())
    cache[name] = mapping
    cache[a['nickname']] = mapping
    atomic(cache_path, dumps(cache))
    return mapping


def allowed_media(url):
    p = up.urlsplit(url)
    return p.scheme == 'https' and any(p.hostname == h or (p.hostname or '').endswith('.' + h) for h in ('qpic.cn', 'qlogo.cn', 'weixin.qq.com'))


def reader_fallback(url, executable):
    try:
        p = subprocess.run([executable, 'read', url, '--strategy', 'auto', '--timeout', '30', '--json'],
                           capture_output=True, timeout=65, encoding='utf-8')
        result = json.loads(p.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise Problem('browser_failed', 'wechat-reader 未返回有效 JSON') from None
    if result.get('status') != 'ok':
        raise Problem(result.get('status', 'browser_failed'), '浏览器兜底未成功；需要时人工完成验证')
    source = result.get('html') or result.get('raw_html')
    if not source:
        raise Problem('browser_format_unsupported', 'CLI 未提供原始 HTML；请保存浏览器页面后用 import-html 导入')
    if not re.search(r'id=[\"\']js_content', source):
        source = '<div id="js_content">' + source + '</div>'
    return source.encode('utf-8'), result


def download_one(store, row, http, refresh_days=30, reader=None, supplied=None, with_media=True):
    a = json.loads(row['payload'])
    old = json.loads(row['content']) if row['content'] else None
    cache_valid = old and all((store.root / old[k]).is_file() for k in ('html_path', 'markdown_path'))
    if supplied is None and row['status'] == 'ok' and cache_valid and time.time() - (row['fetched'] or 0) < refresh_days * 86400:
        content = old
    else:
        raw = None
        try:
            try:
                raw = supplied if supplied is not None else http.get(request_url(a.get('link') or a['canonical_url']))[0]
                content = parse_content(raw)
            except Problem as first:
                if not reader or first.code not in ('parse_failed', 'captcha_required', 'restricted', 'login_or_captcha'):
                    raise
                raw, reader_result = reader_fallback(request_url(a.get('link') or a['canonical_url']), reader)
                content = parse_content(raw)
                content['source_kind'] = 'wechat-reader-inner-html'
                content['reader_result'] = reader_result
                content['title'] = reader_result.get('title') or content.get('title')
                # Upstream author may be the account nickname; don't overwrite author evidence.
                content['reader_account_name'] = reader_result.get('account_name')
            identity = store.get('identity')
            if identity and content.get('biz') and content['biz'] != identity['biz']:
                raise Problem('identity_mismatch', '正文 biz 与账号不一致')
            version = digest(raw)
            folder = store.root / 'articles' / row['id'] / version
            html_path = folder / ('browser-snapshot.html' if content.get('source_kind') else 'original.html')
            atomic(html_path, raw)
            content.update(version=version, fetched_at=time.time(), html_path=str(html_path.relative_to(store.root)),
                           markdown_path=str((folder / 'article.md').relative_to(store.root)))
            content['assets'] = [{'url': u, 'position': i+1, 'status': 'pending'} for i, u in enumerate(content['images'])]
            atomic(folder / 'metadata.json', dumps({'catalog': a, 'content': content}))
        except Problem as e:
            detail = e.record()
            if raw:
                failure = store.root / 'articles' / row['id'] / 'failures' / (digest(raw) + '.html')
                atomic(failure, raw)
                detail['artifact'] = str(failure.relative_to(store.root))
            with store.db:
                store.db.execute('UPDATE articles SET status=?,detail=? WHERE id=?', (e.code, dumps(detail), row['id']))
            return
    # Persist the body before media work so an interruption resumes downloads.
    md_initial = store.root / content['markdown_path']
    if not md_initial.exists():
        atomic(md_initial, content['text'])
    with store.db:
        store.db.execute('UPDATE articles SET status=?,detail=NULL,content=?,fetched=? WHERE id=?',
                         ('ok', dumps(content), content['fetched_at'], row['id']))
    for asset in content['assets']:
        if not with_media:
            continue
        cached = store.db.execute('SELECT payload FROM assets WHERE url=?', (asset['url'],)).fetchone()
        if cached:
            position = asset['position']
            asset.update(json.loads(cached[0]))
            asset['position'] = position
        path = store.root / asset.get('path', '__missing__')
        if asset.get('status') == 'ok' and path.is_file() and digest(path.read_bytes()) == asset.get('sha256'):
            continue
        try:
            if not allowed_media(asset['url']):
                raise Problem('restricted_media_url')
            raw, mime, _ = http.get(asset['url'])
            if not mime.lower().startswith('image/') or not raw:
                raise Problem('media_parse_failed', '图片请求未返回图片')
            key = digest(raw)
            ext = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif', 'image/webp': '.webp', 'image/svg+xml': '.svg'}.get(mime.split(';')[0].lower(), '.img')
            path = store.root / 'media' / (key + ext)
            atomic(path, raw)
            asset.update(status='ok', path=str(path.relative_to(store.root)), sha256=key, bytes=len(raw))
            asset.pop('error', None)
        except Problem as e:
            asset.update(status=e.code, error=e.record())
        with store.db:
            store.db.execute('INSERT OR REPLACE INTO assets VALUES (?,?)', (asset['url'], dumps(asset)))
            store.db.execute('UPDATE articles SET content=? WHERE id=?', (dumps(content), row['id']))
    markdown = content['text']
    md_path = store.root / content['markdown_path']
    for asset in content['assets']:
        target = os.path.relpath(store.root / asset['path'], md_path.parent).replace(os.sep, '/') if asset['status'] == 'ok' else asset['url']
        markdown = markdown.replace(f"ASSET_{asset['position']})", target + ')')
    atomic(md_path, '# ' + (content.get('title') or a['title']) + '\n\n' + markdown + '\n')
    atomic(md_path.parent / 'metadata.json', dumps({'catalog': a, 'content': content}))
    with store.db:
        store.db.execute('UPDATE articles SET status=?,detail=NULL,content=?,fetched=? WHERE id=?',
                         ('ok', dumps(content), content['fetched_at'], row['id']))



def read_single_article(root, url, http, with_media=False, refresh_days=30, reader=None):
    """Read a public article without platform login; persist files and reuse body cache."""
    original_url = request_url(url)
    url = canonical(url)
    if refresh_days < 0:
        raise Problem('invalid_refresh_days')
    folder = root / 'single' / digest(url)[:24]
    store = Store(folder)
    try:
        row = store.db.execute('SELECT * FROM articles WHERE canonical=?', (url,)).fetchone()
        if row is None:
            item = {'source_id': url, 'canonical_url': url, 'link': original_url, 'title': '',
                    'metadata_hash': digest(url), 'create_time': None}
            with store.db:
                store.ingest([item])
            row = store.db.execute('SELECT * FROM articles WHERE canonical=?', (url,)).fetchone()
        else:
            # A fresh share link may restore parameters lost by an earlier caller.
            item = json.loads(row['payload'])
            item['link'] = original_url
            item['observed_urls'] = sorted(set(item.get('observed_urls', []) + [original_url]))
            with store.db:
                store.db.execute('UPDATE articles SET payload=? WHERE id=?', (dumps(item), row['id']))
            row = store.db.execute('SELECT * FROM articles WHERE id=?', (row['id'],)).fetchone()
        old = json.loads(row['content']) if row['content'] else {}
        cached = (row['status'] == 'ok'
                  and all((folder / old.get(k, '__missing__')).is_file() for k in ('html_path', 'markdown_path'))
                  and time.time() - (row['fetched'] or 0) < refresh_days * 86400)
        download_one(store, row, http, refresh_days=refresh_days, reader=reader, with_media=with_media)
        row = store.db.execute('SELECT * FROM articles WHERE id=?', (row['id'],)).fetchone()
        if row['status'] != 'ok':
            detail = json.loads(row['detail']) if row['detail'] else {}
            detail['path'] = str(folder)
            atomic(folder / 'failure.json', dumps(detail))
            atomic(folder / 'read-status.json', dumps({'status': row['status'], 'scope': 'single_article', 'url': url, 'path': str(folder), 'details': detail}))
            raise Problem(row['status'], detail.get('message', row['status']), detail)
        content = json.loads(row['content'])
        item = json.loads(row['payload'])
        item.update(title=content.get('title') or item['title'], create_time=content.get('published_at'),
                    author=content.get('author'))
        with store.db:
            store.db.execute('UPDATE articles SET payload=? WHERE id=?', (dumps(item), row['id']))
        # Preserve legacy single-read artifacts without fetching the article a second time.
        atomic(folder / 'parsed.json', dumps(content))
        if not content.get('source_kind'):
            atomic(folder / 'original.html', (folder / content['html_path']).read_bytes())
        result = {'status': 'ok', 'scope': 'single_article', 'url': url,
                  'title': item['title'], 'nickname': content.get('nickname'), 'author': content.get('author'),
                  'biz': content.get('biz'), 'published_at': content.get('published_at'),
                  'text_chars': len(content['text']), 'images': len(content['images']),
                  'media_requested': with_media, 'unsupported_media': len(content.get('unsupported', [])),
                  'cached': cached, 'retrieval': 'cache' if cached else ('browser' if content.get('source_kind') else 'http'),
                  'fetched_at': content['fetched_at'], 'path': str(folder),
                  'markdown_path': str(folder / content['markdown_path']),
                  'html_path': str(folder / content['html_path']),
                  'metadata_path': str((folder / content['markdown_path']).parent / 'metadata.json')}
        if with_media:
            result['archive'] = report(store)
        atomic(folder / 'read-status.json', dumps(result))
        return result
    finally:
        store.close()


def download_all(store, http, max_articles=100000, refresh_days=30, reader=None):
    rows = store.db.execute('SELECT * FROM articles ORDER BY attempted ASC,id').fetchall()
    for row in rows[:max_articles]:
        download_one(store, row, http, refresh_days, reader)
        with store.db:
            store.db.execute('UPDATE articles SET attempted=? WHERE id=?', (time.time(), row['id']))
    return min(len(rows), max_articles)


def report(store):
    run = store.get('run', {})
    items, missing, bodies, asset_missing, unsupported = [], [], 0, 0, 0
    dates = []
    for row in store.db.execute('SELECT * FROM articles ORDER BY id'):
        a = json.loads(row['payload'])
        c = json.loads(row['content']) if row['content'] else {}
        status = row['status']
        if status == 'ok' and not all((store.root / c.get(k, '__missing__')).is_file() for k in ('html_path', 'markdown_path')):
            status = 'cache_missing'
        bodies += status == 'ok'
        assets = c.get('assets', [])
        failed = [x for x in assets if x['status'] != 'ok' or not (store.root / x.get('path', '__missing__')).is_file()
                  or digest((store.root / x['path']).read_bytes()) != x.get('sha256')]
        asset_missing += len(failed)
        unsupported += len(c.get('unsupported', []))
        published = c.get('published_at') or a.get('create_time')
        entry = {'id': row['id'], 'title': a['title'], 'author': c.get('author') or a.get('author'),
                 'original': c.get('original'), 'published_at': published,
                 'after_cutoff': bool(published and int(published) > run.get('cutoff', float('inf'))),
                 'original_url': a['link'], 'canonical_url': a['canonical_url'], 'status': status,
                 'directory_presence': ('present' if a.get('catalog_run') == run.get('id') and a.get('catalog_pass') == run.get('pass')
                                        else 'absent_from_latest_scan' if run.get('status') == 'stable' else 'not_checked_this_run'),
                 'media_missing': len(failed), 'media_unsupported': len(c.get('unsupported', [])),
                 'markdown': c.get('markdown_path'), 'version': c.get('version'), 'last_seen': row['last_seen']}
        items.append(entry)
        if published:
            dates.append(int(published))
        if status != 'ok' or failed or c.get('unsupported'):
            missing.append(dict(entry, error=json.loads(row['detail']) if row['detail'] else None,
                                assets=failed, unsupported=c.get('unsupported', [])))
    paused = store.get('directory_pause')
    stable = run.get('status') == 'stable' and not paused
    passes = run.get('passes', [])
    last = passes[-1] if passes else {}
    totals = set(last.get('totals', []))
    count_check = 'matches_observed_batches' if len(totals) == 1 and next(iter(totals)) == last.get('end') else 'unknown_or_mismatch'
    result = {'backend': BACKEND, 'identity': store.get('identity'), 'run_id': run.get('id'),
              'cutoff': run.get('cutoff'), 'finished_at': run.get('finished_at'),
              'directory': {'status': 'stable_observed' if stable else 'partial', 'complete': False,
                            'boundary': '公众平台当前可见发布目录；无法核验隐藏/删除且无索引内容',
                            'stable_passes': len(passes), 'observed_batches': last.get('end'),
                            'reported_total': sorted(totals) if totals else None, 'total_unit': 'unknown',
                            'count_check': count_check, 'terminal_checks': last.get('tail_checks', 0),
                            'reason': '真实分页计数单位尚待账号登录实测；两轮一致仅证明观测稳定',
                            'warnings': run.get('warnings', []), 'problem': paused or run.get('problem'), 'checkpoint_begin': run.get('begin')},
              'discovered': len(items), 'body_success': bodies, 'body_missing': len(items)-bodies,
              'body_complete_for_discovered': bool(items) and bodies == len(items),
              'media_missing': asset_missing, 'media_unknown_articles': len(items)-bodies, 'media_unsupported': unsupported,
              'media_complete_for_downloaded': bodies > 0 and not asset_missing and not unsupported,
              'absent_from_latest_scan': sum(x['directory_presence'] == 'absent_from_latest_scan' for x in items),
              'all_complete': False, 'article_time_range': [min(dates), max(dates)] if dates else None,
              'paths': {'catalog': str(store.root / 'catalog.jsonl'), 'missing': str(store.root / 'missing.json'),
                        'database': str(store.root / 'archive.sqlite'), 'report': str(store.root / 'report.json')}}
    public = store.get('public_catalog')
    if public is not None:
        result.update(backend='public-links-v1', finished_at=public.get('finished_at'), public_catalog=public)
        result['directory'] = {'status': 'partial', 'complete': False, 'reported_total': None,
                               'total_unit': 'unknown', 'scope': 'discovered_public_links',
                               'boundary': '公开合集和已发现链接；账号全历史总数未知',
                               'reason': '清单只证明已发现范围，不能排除未收录文章',
                               'problem': public.get('stop_reason')}
    atomic(store.root / 'catalog.jsonl', ''.join(dumps(x)+'\n' for x in items))
    atomic(store.root / 'missing.json', dumps(missing))
    atomic(store.root / 'report.json', dumps(result))
    with (store.root / 'catalog.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(items[0]) if items else ['id','title','status'])
        writer.writeheader()
        writer.writerows(items)
    lines = ['# 公众号归档核查', '', f"目录：{result['directory']['status']}；全历史完整：未证明。",
             f"发现 {len(items)} 篇；正文成功 {bodies}；正文缺失 {len(items)-bodies}；图片缺失 {asset_missing}；未支持媒体 {unsupported}。",
             f"已完成扫描轮数 {len(passes)}；报告总数 {result['directory']['reported_total']}；单位 unknown。",
             f"检查点 begin={run.get('begin')}；问题：{dumps(run.get('problem'))}", '',
             ('公开链接清单归档，未执行公众平台全目录扫描。' if public is not None else '目录扫描、重叠检查与末页探测的实际证据见 archive.sqlite/evidence。'),
             '缺失详情见 missing.json；可检索目录见 catalog.csv / catalog.jsonl。',
             '已删除、隐藏且没有索引的文章无法从本报告确认存在或恢复；不能宣称无遗漏。']
    atomic(store.root / 'report.md', '\n'.join(lines)+'\n')
    return result


@contextlib.contextmanager
def lock(root):
    path = root / '.lock'
    f = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if path.stat().st_size == 0:
                f.write(b'0'); f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise Problem('already_running') from None
    try:
        yield
    finally:
        f.close()


def login(root, channel='msedge', timeout=600):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise Problem('browser_dependency', '请先用 scripts/prepare_login.ps1 安装独立浏览器依赖') from None
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel, headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto('https://mp.weixin.qq.com/', wait_until='domcontentloaded')
        print(dumps({'phase': 'scan_required', 'message': '请在打开的公众平台窗口使用自己的管理员微信扫码登录', 'timeout_seconds': timeout}), flush=True)
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            token = up.parse_qs(up.urlsplit(page.url).query).get('token', [''])[0]
            if token:
                cookies = context.cookies('https://mp.weixin.qq.com/')
                cookie = '; '.join(c['name']+'='+c['value'] for c in cookies)
                if cookie:
                    path = root / 'session.json'
                    atomic(path, dumps({'token': token, 'cookie': cookie, 'captured_at': time.time()}))
                    os.chmod(path, 0o600)
                    browser.close()
                    return {'phase': 'session_saved', 'path': str(path), 'message': '登录态只保存在独立数据目录；不要发送或提交此文件'}
            page.wait_for_timeout(1000)
        browser.close()
        raise Problem('login_timeout', '扫码等待结束；未保存有效登录态')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', type=Path, default=default_root())
    p.add_argument('--interval', type=float, default=2)
    sub = p.add_subparsers(dest='command', required=True)
    l = sub.add_parser('login'); l.add_argument('--channel', default='msedge'); l.add_argument('--timeout', type=int, default=600)
    sub.add_parser('doctor')
    r = sub.add_parser('run'); r.add_argument('name'); r.add_argument('--select-fakeid'); r.add_argument('--sample-url')
    r.add_argument('--max-pages', type=int, default=10000); r.add_argument('--max-articles', type=int, default=100000)
    r.add_argument('--refresh-days', type=int, default=30); r.add_argument('--reader')
    r.add_argument('--bodies-only', action='store_true'); r.add_argument('--archive', type=Path)
    q = sub.add_parser('report'); q.add_argument('archive', type=Path)
    x = sub.add_parser('read-url'); x.add_argument('url'); x.add_argument('--with-media', action='store_true')
    x.add_argument('--refresh-days', type=float, default=30); x.add_argument('--reader')
    x = sub.add_parser('import-html'); x.add_argument('archive', type=Path); x.add_argument('id'); x.add_argument('html_file', type=Path)
    args = p.parse_args(argv)
    store = None
    try:
        root = safe_root(args.data_root)
        marker = root / '.wechat-account-archive-data'
        known = {'accounts', 'single', '.venv', 'session.json', 'identities.json', 'identity-page.json', 'search.json', '.lock'}
        if root.exists() and not marker.exists() and any(p.name not in known for p in root.iterdir()):
            raise Problem('unsafe_data_root', '目录包含其他数据；请使用专用归档目录')
        root.mkdir(parents=True, exist_ok=True)
        if not marker.exists():
            atomic(marker, dumps({'backend': BACKEND, 'schema': 1}))
        if args.interval < 0:
            raise Problem('invalid_interval')
        http = HTTP(args.interval)
        if args.command == 'doctor':
            import shutil
            print(dumps({'data_root': str(root), 'session_present': (root / 'session.json').is_file(),
                         'wechat_reader': shutil.which('wechat-reader'), 'backend': BACKEND,
                         'login_entry': 'https://mp.weixin.qq.com/'}))
            return 0
        with lock(root):
            if args.command == 'login':
                result = login(root, args.channel, args.timeout)
            elif args.command == 'read-url':
                result = read_single_article(root, args.url, http, args.with_media, args.refresh_days, args.reader)
            elif args.command in ('report', 'import-html'):
                folder = safe_root(args.archive)
                store = Store(folder)
                if args.command == 'import-html':
                    row = store.db.execute('SELECT * FROM articles WHERE id=?', (args.id,)).fetchone()
                    if not row:
                        raise Problem('unknown_article')
                    download_one(store, row, http, supplied=args.html_file.read_bytes())
                result = report(store)
            else:
                if args.max_pages < 1 or args.max_articles < 0 or args.refresh_days < 0:
                    raise Problem('invalid_budget')
                if args.bodies_only:
                    if not args.archive:
                        raise Problem('archive_required', '--bodies-only 需要 --archive；不依赖目录登录态')
                    folder = safe_root(args.archive)
                    store = Store(folder)
                else:
                    try:
                        backend = Platform(root / 'session.json', http)
                        identity = resolve_account(backend, args.name, root, http, args.select_fakeid, args.sample_url)
                    except Problem as e:
                        recoverable = {'login_required', 'login_or_captcha', 'captcha_required', 'network_error', 'rate_limited'}
                        mappings = json.loads((root / 'identities.json').read_text(encoding='utf-8')) if (root / 'identities.json').exists() else {}
                        identity = mappings.get(args.name)
                        if e.code not in recoverable or not identity or identity.get('backend') != BACKEND:
                            raise
                        folder = root / 'accounts' / digest(BACKEND + ':' + identity['fakeid'])[:24]
                        if not (folder / 'archive.sqlite').exists():
                            raise
                        store = Store(folder)
                        with store.db:
                            store.put('directory_pause', e.record())
                    else:
                        folder = root / 'accounts' / digest(BACKEND + ':' + identity['fakeid'])[:24]
                        store = Store(folder)
                        with store.db:
                            store.put('identity', identity)
                            store.put('directory_pause', None)
                        enumerate_history(store, backend, identity['fakeid'], args.max_pages)
                download_all(store, http, args.max_articles, args.refresh_days, args.reader)
                result = report(store)
            print(dumps(result))
            return 0
    except KeyboardInterrupt:
        if store:
            report(store)
        print(dumps({'status': 'interrupted', 'message': '已保存检查点；重复同一命令继续'}))
        return 130
    except Problem as e:
        if store:
            report(store)
        print(dumps({'status': e.code, 'message': e.message, 'details': e.details}))
        return 2
    except (OSError, ValueError, sqlite3.Error) as e:
        print(dumps({'status': 'local_error', 'type': type(e).__name__, 'message': '本地读写或格式错误；未输出可能含凭据的异常文本'}))
        return 2
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
