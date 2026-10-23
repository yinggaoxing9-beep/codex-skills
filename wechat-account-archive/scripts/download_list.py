#!/usr/bin/env python3
"""Download an already-discovered public article list, without platform login."""
import argparse
import json
from pathlib import Path
import time
import archive as a


def ingest_list(store, records, expected_biz, name):
    identity = store.get('identity')
    if identity and identity.get('biz') != expected_biz:
        raise a.Problem('identity_mismatch', '已有归档账号与目标账号不一致')
    items = []
    for record in records:
        link = a.request_url(record.get('url') or record.get('link') or '')
        canonical = a.canonical(link)
        if a.biz(link) and a.biz(link) != expected_biz:
            raise a.Problem('identity_mismatch', '清单包含其他账号的文章')
        existing = store.db.execute('SELECT payload FROM articles WHERE canonical=?', (canonical,)).fetchone()
        item = json.loads(existing[0]) if existing else {
            'source_id': canonical, 'canonical_url': canonical,
            'metadata_hash': a.digest(canonical), 'create_time': record.get('create_time')}
        item.update(link=link, title=record.get('title') or item.get('title', ''),
                    discovery_source=record.get('discovery_source', 'public_link_list'))
        items.append(item)
    with store.db:
        store.put('identity', identity or {'biz': expected_biz, 'nickname': name, 'source': 'public_links'})
        store.put('public_catalog', {'scope': 'discovered_public_links', 'account_total': None,
                                    'input_records': len(records), 'imported_at': time.time()})
        store.ingest(items)
    return a.report(store)


def download(store, http, with_media=False, max_articles=100000, refresh_days=30):
    attempted = 0
    blocked = 0
    stop = None
    rows = store.db.execute('SELECT * FROM articles ORDER BY attempted ASC,id').fetchall()
    for row in rows:
        content = json.loads(row['content']) if row['content'] else {}
        cached = (row['status'] == 'ok' and time.time() - (row['fetched'] or 0) < refresh_days * 86400
                  and all((store.root / content.get(k, '__missing__')).is_file() for k in ('html_path', 'markdown_path')))
        if cached:
            continue
        if attempted >= max_articles:
            stop = 'article_budget'
            break
        a.download_one(store, row, http, refresh_days=refresh_days, with_media=False)
        attempted += 1
        with store.db:
            store.db.execute('UPDATE articles SET attempted=? WHERE id=?', (time.time(), row['id']))
        current = store.db.execute('SELECT status FROM articles WHERE id=?', (row['id'],)).fetchone()[0]
        print(a.dumps({'phase': 'body', 'attempted': attempted, 'title': json.loads(row['payload'])['title'], 'status': current}), flush=True)
        blocked = blocked + 1 if current in ('captcha_required', 'rate_limited', 'restricted', 'network_error') else 0
        if blocked >= 3:
            stop = 'consecutive_access_failures'
            break
    with store.db:
        state = store.get('public_catalog', {})
        state.update(finished_at=time.time(), stop_reason=stop, attempted_this_run=attempted)
        store.put('public_catalog', state)
    # Commit and report all bodies before optional image work.
    a.report(store)
    if with_media:
        for row in store.db.execute("SELECT * FROM articles WHERE status='ok' ORDER BY id").fetchall():
            # Reuse body even when this invocation explicitly refreshed it already.
            a.download_one(store, row, http, refresh_days=365000, with_media=True)
            c=json.loads(store.db.execute('SELECT content FROM articles WHERE id=?', (row['id'],)).fetchone()[0])
            print(a.dumps({'phase': 'media', 'title': json.loads(row['payload'])['title'],
                           'images': len(c['assets']), 'missing': sum(x['status'] != 'ok' for x in c['assets'])}), flush=True)
    return a.report(store)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path, required=True, help='UTF-8 JSONL with url/title/create_time')
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--biz', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--with-media', action='store_true')
    p.add_argument('--interval', type=float, default=2)
    p.add_argument('--max-articles', type=int, default=100000)
    p.add_argument('--refresh-days', type=float, default=30)
    args=p.parse_args()
    if args.interval < 0 or args.max_articles < 0 or args.refresh_days < 0:
        p.error('budgets must be nonnegative')
    folder=a.safe_root(args.archive)
    folder.mkdir(parents=True, exist_ok=True)
    store=None
    try:
        records=[json.loads(line) for line in args.catalog.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        with a.lock(folder):
            store=a.Store(folder)
            ingest_list(store, records, args.biz, args.name)
            result=download(store, a.HTTP(args.interval), args.with_media, args.max_articles, args.refresh_days)
            print(a.dumps(result))
            return 0 if result['body_complete_for_discovered'] and (not args.with_media or result['media_complete_for_downloaded']) else 2
    except KeyboardInterrupt:
        if store: a.report(store)
        print(a.dumps({'status':'interrupted', 'message':'进度已保存；重复同一命令继续'}))
        return 130
    except (a.Problem, OSError, ValueError) as e:
        if store: a.report(store)
        print(a.dumps({'status': e.code if isinstance(e,a.Problem) else 'local_error'}))
        return 2
    finally:
        if store: store.close()


if __name__ == '__main__':
    raise SystemExit(main())
