import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import archive as a


def article(i, **changes):
    x = {'aid': str(i), 'title': 'title '+str(i), 'link': 'https://mp.weixin.qq.com/s?__biz=account&mid='+str(i)+'&idx=1&sn=s',
         'create_time': 1700000000, 'update_time': 1700000000, 'author': 'writer'}
    x.update(changes)
    return x


def page(groups, total=None):
    p = {'publish_list': [{'publish_info': a.dumps({'appmsgex': g})} for g in groups]}
    if total is not None:
        p['total_count'] = total
    return {'base_resp': {'ret': 0}, 'publish_page': a.dumps(p)}


BODY = b'<h1 id="activity-name">Title</h1><a id="js_name">Account</a><span id="js_author_name">Writer</span><div id="js_content"><p>Hello</p><img data-src="https://mmbiz.qpic.cn/a.png"></div><script>var biz="account"; var ct="1700000000";</script>'


class Backend:
    def __init__(self, groups, total=None):
        self.groups, self.total, self.calls = groups, total, []
    def page(self, fid, begin, count):
        self.calls.append((begin,count))
        return page(self.groups[begin:begin+count], self.total)


class HTTP:
    def __init__(self, body=BODY, media_ok=True):
        self.body, self.media_ok, self.calls = body, media_ok, []
    def get(self, url, *args, **kwargs):
        self.calls.append(url)
        if 'qpic.cn' in url:
            if not self.media_ok:
                raise a.Problem('network_error')
            return b'\x89PNG\r\n\x1a\nimage', 'image/png', url
        return self.body, 'text/html', url


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = a.Store(self.root / 'account')
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def ingest(self, *items):
        with self.store.db:
            self.store.ingest(a.parse_page(page([list(items)]))[1])
    def row(self):
        return self.store.db.execute('SELECT * FROM articles ORDER BY id').fetchone()
    def size(self):
        return self.store.db.execute('SELECT count(*) FROM articles').fetchone()[0]

    def test_multi_article_push_uses_batch_offset(self):
        b=Backend([[article(1),article(2)], [article(3)], [article(4),article(5)]],3)
        r=a.enumerate_history(self.store,b,'fid',page_size=1)
        self.assertEqual(r['status'],'stable'); self.assertEqual(self.size(),5)
        self.assertIn((1,1),b.calls); self.assertEqual(r['passes'][-1]['end'],3)

    def test_article_total_not_batch_count(self):
        r=a.enumerate_history(self.store,Backend([[article(1),article(2)],[article(3)]],3),'fid',page_size=1)
        self.assertEqual(r['status'],'stable')
        report=a.report(self.store)
        self.assertEqual(report['directory']['total_unit'],'unknown')
        self.assertEqual(report['directory']['count_check'],'unknown_or_mismatch')
        self.assertFalse(report['all_complete'])

    def test_unknown_total_remains_null(self):
        a.enumerate_history(self.store,Backend([[article(1)]]),'fid')
        self.assertIsNone(a.report(self.store)['directory']['reported_total'])

    def test_transient_empty_recovers_without_early_finish(self):
        class Empty(Backend):
            def page(self,fid,begin,count):
                if begin==1 and not getattr(self,'glitched',False):
                    self.glitched=True; return page([],3)
                return super().page(fid,begin,count)
        r=a.enumerate_history(self.store,Empty([[article(1)],[article(2)],[article(3)]],3),'fid',page_size=1)
        self.assertEqual(r['status'],'stable'); self.assertEqual(self.size(),3)
        self.assertTrue(r['warnings'])

    def test_persistent_empty_before_other_data_fails(self):
        class Empty(Backend):
            def page(self,fid,begin,count):
                return page([],3) if begin==1 else super().page(fid,begin,count)
        r=a.enumerate_history(self.store,Empty([[article(1)],[article(2)],[article(3)]],3),'fid',page_size=1)
        self.assertEqual(r['problem']['code'],'unexpected_empty'); self.assertEqual(r['begin'],1)

    def test_repeated_page_fails(self):
        class Repeat(Backend):
            def page(self,fid,begin,count):
                return page([[article(1)]],3)
        r=a.enumerate_history(self.store,Repeat([],3),'fid',page_size=1)
        self.assertEqual(r['problem']['code'],'repeated_page')
        self.assertFalse(a.report(self.store)['directory']['complete'])

    def test_parse_failure_preserves_page_and_cursor(self):
        class Broken(Backend):
            def page(self,fid,begin,count):
                return {'base_resp':{'ret':0},'publish_page':{'publish_list':[{'publish_info':'{bad'}]}}
        r=a.enumerate_history(self.store,Broken([]),'fid')
        self.assertEqual(r['problem']['code'],'parse_failed'); self.assertEqual(r['begin'],0)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM evidence').fetchone()[0],1)
        self.assertEqual(a.enumerate_history(self.store,Backend([[article(1)]]),'fid')['status'],'stable')

    def test_checkpoint_resume(self):
        b=Backend([[article(1)],[article(2)],[article(3)]],3)
        first=a.enumerate_history(self.store,b,'fid',max_pages=1,page_size=1)
        self.assertEqual(first['problem']['code'],'page_budget'); self.assertEqual(first['begin'],1)
        b.calls=[]
        final=a.enumerate_history(self.store,b,'fid',page_size=1)
        self.assertEqual(b.calls[0],(1,1)); self.assertEqual(first['id'],final['id'])
        self.assertEqual(final['status'],'stable')

    def test_same_timestamp_incremental_articles_retained(self):
        b=Backend([[article(1)],[article(2)]],2)
        a.enumerate_history(self.store,b,'fid',page_size=1)
        b.groups.insert(0,[article(3)]); b.total=3
        a.enumerate_history(self.store,b,'fid',page_size=1)
        self.assertEqual(self.size(),3)

    def test_inflight_offset_drift(self):
        b=Backend([[article(1)],[article(2)]],2)
        a.enumerate_history(self.store,b,'fid',max_pages=1,page_size=1)
        b.groups.insert(0,[article(3)]); b.total=3
        r=a.enumerate_history(self.store,b,'fid',page_size=1)
        self.assertEqual(r['problem']['code'],'offset_drift'); self.assertEqual(r['begin'],0)
        self.assertEqual(a.enumerate_history(self.store,b,'fid',page_size=1)['status'],'stable')
        self.assertEqual(self.size(),3)

    def test_duplicate_tracking_urls_merge(self):
        self.ingest(article(1),article(1,link=article(1)['link']+'&scene=1'))
        self.assertEqual(self.size(),1)
        self.assertEqual(len(a.json.loads(self.row()['payload'])['observed_urls']),2)

    def test_body_failure_not_complete(self):
        self.ingest(article(1)); a.download_all(self.store,HTTP(b'<html>200 empty</html>'))
        r=a.report(self.store)
        self.assertEqual(r['body_success'],0); self.assertFalse(r['body_complete_for_discovered'])
        self.assertFalse(r['all_complete'])
        self.assertEqual(a.json.loads((self.store.root/'missing.json').read_text())[0]['status'],'parse_failed')

    def test_image_only_and_media_retry(self):
        self.ingest(article(1))
        h=HTTP(b'<div id="js_content"><img data-src="https://mmbiz.qpic.cn/a.png"></div>',False)
        a.download_all(self.store,h); r=a.report(self.store)
        self.assertEqual(r['body_success'],1); self.assertEqual(r['media_missing'],1)
        self.assertFalse(r['media_complete_for_downloaded'])
        h.calls=[]; h.media_ok=True; a.download_all(self.store,h)
        self.assertEqual(len(h.calls),1); self.assertEqual(a.report(self.store)['media_missing'],0)

    def test_cache_and_content_versions(self):
        self.ingest(article(1)); h=HTTP(); a.download_all(self.store,h)
        h.calls=[]; a.download_all(self.store,h); self.assertEqual(h.calls,[])
        self.ingest(article(1,update_time=1700000001)); h.body=BODY.replace(b'Hello',b'Updated')
        a.download_all(self.store,h)
        self.assertEqual(len(list((self.store.root/'articles').glob('*/*/original.html'))),2)

    def test_cache_missing_is_retried(self):
        self.ingest(article(1)); h=HTTP(); a.download_all(self.store,h)
        c=a.json.loads(self.row()['content']); (self.store.root/c['html_path']).unlink()
        self.assertEqual(a.report(self.store)['body_missing'],1)
        a.download_all(self.store,h); self.assertEqual(a.report(self.store)['body_success'],1)

    def test_media_order_duplicate_cache_shared(self):
        self.ingest(article(1),article(2))
        h=HTTP(b'<div id="js_content"><img data-src="https://mmbiz.qpic.cn/a.png"><p>between</p><img data-src="https://mmbiz.qpic.cn/a.png"></div>')
        a.download_all(self.store,h)
        self.assertEqual(sum('qpic.cn' in u for u in h.calls),1)
        c=a.json.loads(self.row()['content'])
        self.assertEqual([x['position'] for x in c['assets']],[1,2])
        self.assertIn('between',(self.store.root/c['markdown_path']).read_text())

    def test_blocked_statuses_separate(self):
        for text,code in [('验证码','captcha_required'),('操作频繁','rate_limited'),('该内容已被发布者删除','deleted'),('付费阅读','restricted')]:
            with self.subTest(code=code):
                with self.assertRaises(a.Problem) as cm: a.parse_content('<html>'+text+'</html>')
                self.assertEqual(cm.exception.code,code)

    def test_nested_secrets_redacted(self):
        safe=a.dumps(a.redact({'publish_page':a.dumps({'token':'SECRET','publish_info':a.dumps({'cookie':'PRIVATE'})})}))
        self.assertNotIn('SECRET',safe); self.assertNotIn('PRIVATE',safe)

    def test_skill_data_root_refused(self):
        with self.assertRaises(a.Problem): a.safe_root(Path(__file__).parents[1]/'data')

    def test_body_retry_independent_of_directory_login(self):
        self.ingest(article(1)); a.download_all(self.store,HTTP('<html>验证码</html>'.encode()))
        self.assertEqual(self.row()['status'],'captcha_required')
        a.download_all(self.store,HTTP()); self.assertEqual(self.row()['status'],'ok')

    def test_identity_independent_article_evidence(self):
        b=Backend([[article(1)]],1)
        b.search_page=lambda q,begin,count:{'base_resp':{'ret':0},'list':[{'fakeid':'fid','nickname':'Account','alias':'stable-alias'}]}
        self.assertEqual(a.resolve_account(b,'Account',self.root,HTTP())['biz'],'account')
        with self.assertRaises(a.Problem) as cm:
            a.resolve_account(b,'Account',self.root,HTTP(BODY.replace(b'Account',b'Other')))
        self.assertEqual(cm.exception.code,'identity_unverified')

    def test_homonyms_require_selection(self):
        b=Backend([[article(1)]],1)
        b.search_page=lambda q,begin,count:{'base_resp':{'ret':0},'list':[{'fakeid':str(i),'nickname':'Account','alias':str(i)} for i in (1,2)]}
        with self.assertRaises(a.Problem) as cm: a.resolve_account(b,'Account',self.root,HTTP())
        self.assertEqual(cm.exception.code,'identity_ambiguous')


    def test_actual_interruption_checkpoint_survives_reopen(self):
        class Interrupt(Backend):
            def page(self,fid,begin,count):
                if begin == 1: raise KeyboardInterrupt()
                return super().page(fid,begin,count)
        with self.assertRaises(KeyboardInterrupt):
            a.enumerate_history(self.store,Interrupt([[article(1)],[article(2)]],2),'fid',page_size=1)
        location=self.store.root; self.store.close(); self.store=a.Store(location)
        self.assertEqual(self.store.get('run')['begin'],1)
        self.assertEqual(a.enumerate_history(self.store,Backend([[article(1)],[article(2)]],2),'fid',page_size=1)['status'],'stable')

    def test_body_saved_before_interrupted_media_download(self):
        self.ingest(article(1))
        class Interrupt(HTTP):
            def get(self,url,*args,**kwargs):
                if 'qpic.cn' in url: raise KeyboardInterrupt()
                return super().get(url,*args,**kwargs)
        with self.assertRaises(KeyboardInterrupt): a.download_all(self.store,Interrupt())
        self.assertEqual(self.row()['status'],'ok')
        h=HTTP(); a.download_all(self.store,h)
        self.assertEqual(len(h.calls),1)
        self.assertEqual(a.report(self.store)['media_missing'],0)

    def test_bounded_body_queue_progresses(self):
        self.ingest(article(1),article(2),article(3))
        for _ in range(3): a.download_all(self.store,HTTP(),max_articles=1)
        self.assertEqual(a.report(self.store)['body_success'],3)

    def test_removed_catalog_entries_remain_visible(self):
        b=Backend([[article(1)],[article(2)]],2)
        a.enumerate_history(self.store,b,'fid',page_size=1)
        b.groups=[[article(2)]]; b.total=1
        a.enumerate_history(self.store,b,'fid',page_size=1)
        self.assertEqual(a.report(self.store)['absent_from_latest_scan'],1)
        self.assertEqual(self.size(),2)

    def test_corrupt_asset_report_and_repair(self):
        self.ingest(article(1)); a.download_all(self.store,HTTP())
        c=a.json.loads(self.row()['content'])
        asset=self.store.root/c['assets'][0]['path']; asset.write_bytes(b'corrupt')
        self.assertEqual(a.report(self.store)['media_missing'],1)
        a.download_all(self.store,HTTP()); self.assertEqual(a.report(self.store)['media_missing'],0)

    def test_paywall_teaser_not_body_success(self):
        with self.assertRaises(a.Problem) as cm:
            a.parse_content('<script>var is_pay_subscribe=1;</script><div id="js_content">teaser</div>')
        self.assertEqual(cm.exception.code,'restricted')

    def test_browser_reader_inner_html_adapter(self):
        result={'status':'ok','html':'<p>Browser body</p>','title':'Browser title','author':'Account'}
        process=type('Result',(),{'stdout':a.dumps(result)})()
        with patch.object(a.subprocess,'run',return_value=process):
            raw,provenance=a.reader_fallback(article(1)['link'],'reader')
        self.assertEqual(a.parse_content(raw)['text'],'Browser body')
        self.assertEqual(provenance,result)

    def test_empty_archive_does_not_claim_success(self):
        r=a.report(self.store)
        self.assertFalse(r['body_complete_for_discovered'])
        self.assertFalse(r['media_complete_for_downloaded'])
        self.assertFalse(r['all_complete'])


    def test_request_budget_includes_overlap_and_tail_probes(self):
        b=Backend([[article(1)],[article(2)]],2)
        a.enumerate_history(self.store,b,'fid',max_pages=1,page_size=1)
        b.calls=[]
        r=a.enumerate_history(self.store,b,'fid',max_pages=1,page_size=1)
        self.assertEqual(len(b.calls),1)
        self.assertEqual(r['problem']['code'],'page_budget')
        self.assertEqual(r['begin'],1)

    def test_unstable_pass_cannot_be_reused_as_second_scan(self):
        b=Backend([[article(1)]],1)
        r=a.enumerate_history(self.store,b,'fid',max_passes=1)
        self.assertEqual(r['problem']['code'],'unstable_history')
        self.assertEqual(r['begin'],0)
        b.groups=[[article(2)]]
        r=a.enumerate_history(self.store,b,'fid',max_passes=1)
        self.assertNotEqual(r['status'],'stable')
        self.assertEqual(self.size(),2)


    def test_home_directory_cannot_be_data_root(self):
        with self.assertRaises(a.Problem): a.safe_root(Path.home())

    def test_name_run_continues_known_bodies_when_login_expires(self):
        import io
        import contextlib
        data=self.root/'independent-data'; data.mkdir()
        identity={'backend':a.BACKEND,'fakeid':'fid','nickname':'Account','biz':'account'}
        a.atomic(data/'identities.json',a.dumps({'Account':identity}))
        folder=data/'accounts'/a.digest(a.BACKEND+':fid')[:24]
        with_store=a.Store(folder)
        with with_store.db:
            with_store.ingest(a.parse_page(page([[article(1)]]))[1])
            with_store.put('identity',identity)
        with_store.close()
        output=io.StringIO()
        with patch.object(a,'HTTP',return_value=HTTP()),contextlib.redirect_stdout(output):
            status=a.main(['--data-root',str(data),'run','Account'])
        result=a.json.loads(output.getvalue())
        self.assertEqual(status,0); self.assertEqual(result['body_success'],1)
        self.assertEqual(result['directory']['problem']['code'],'login_required')
        self.assertEqual(result['directory']['status'],'partial')



    def test_link_cli_needs_no_login_or_browser_and_returns_body_path(self):
        import io
        import contextlib
        h=HTTP(); output=io.StringIO()
        with patch.object(a,'HTTP',return_value=h), patch.object(a,'Platform') as platform, patch.object(a,'reader_fallback') as browser, contextlib.redirect_stdout(output):
            status=a.main(['--data-root',str(self.root/'single-data'),'read-url',article(1)['link']])
        result=a.json.loads(output.getvalue())
        self.assertEqual(status,0); self.assertEqual(result['retrieval'],'http')
        self.assertEqual(result['scope'],'single_article')
        platform.assert_not_called(); browser.assert_not_called()
        self.assertEqual(h.calls,[a.canonical(article(1)['link'])])
        markdown=Path(result['markdown_path']).read_text(encoding='utf-8')
        self.assertIn('Hello',markdown); self.assertIn('https://mmbiz.qpic.cn/a.png',markdown)
        self.assertNotIn('ASSET_',markdown)
        self.assertNotIn('archive',result)
        self.assertFalse((self.root/'single-data'/'session.json').exists())

    def test_single_url_cache_and_forced_refresh_preserve_versions(self):
        h=HTTP(); url=article(1)['link']
        first=a.read_single_article(self.root,url,h)
        h.calls=[]
        cached=a.read_single_article(self.root,url+'#wechat_redirect',h)
        self.assertEqual(h.calls,[]); self.assertTrue(cached['cached'])
        self.assertEqual(cached['markdown_path'],first['markdown_path'])
        h.body=BODY.replace(b'Hello',b'Revised')
        fresh=a.read_single_article(self.root,url,h,refresh_days=0)
        self.assertEqual(len(h.calls),1); self.assertFalse(fresh['cached'])
        self.assertIn('Revised',Path(fresh['markdown_path']).read_text())
        self.assertNotEqual(first['markdown_path'],fresh['markdown_path'])
        self.assertTrue(Path(first['markdown_path']).is_file())

    def test_single_url_media_added_without_refetching_body(self):
        h=HTTP(); url=article(1)['link']
        first=a.read_single_article(self.root,url,h)
        h.calls=[]
        result=a.read_single_article(self.root,url,h,with_media=True)
        self.assertEqual(h.calls,['https://mmbiz.qpic.cn/a.png'])
        self.assertEqual(result['retrieval'],'cache')
        self.assertEqual(result['archive']['body_success'],1)
        self.assertEqual(result['archive']['media_missing'],0)
        self.assertFalse(result['archive']['all_complete'])
        self.assertNotIn('https://mmbiz.qpic.cn/a.png',Path(result['markdown_path']).read_text())

    def test_single_url_failed_refresh_does_not_return_old_success(self):
        url=article(1)['link']; h=HTTP()
        old=a.read_single_article(self.root,url,h)
        h.body='<html>验证码</html>'.encode()
        with patch.object(a,'reader_fallback') as browser:
            with self.assertRaises(a.Problem) as cm:
                a.read_single_article(self.root,url,h,refresh_days=0)
        self.assertEqual(cm.exception.code,'captcha_required'); browser.assert_not_called()
        self.assertTrue(Path(old['markdown_path']).is_file())
        state=a.json.loads((Path(old['path'])/'read-status.json').read_text(encoding='utf-8'))
        self.assertEqual(state['status'],'captcha_required')

    def test_single_url_browser_only_when_explicit_and_http_failed(self):
        h=HTTP('<html>验证码</html>'.encode())
        with patch.object(a,'reader_fallback',return_value=(BODY,{'status':'ok','title':'Browser title'})) as browser:
            result=a.read_single_article(self.root,article(1)['link'],h,reader='test-reader')
        browser.assert_called_once_with(a.canonical(article(1)['link']),'test-reader')
        self.assertEqual(result['retrieval'],'browser')
        self.assertEqual(result['title'],'Browser title')
        self.assertTrue(result['html_path'].endswith('browser-snapshot.html'))

    def test_single_url_media_failure_kept_separate_from_body(self):
        result=a.read_single_article(self.root,article(1)['link'],HTTP(media_ok=False),with_media=True)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['archive']['body_success'],1)
        self.assertEqual(result['archive']['media_missing'],1)
        self.assertFalse(result['archive']['media_complete_for_downloaded'])

    def test_single_url_rejects_non_wechat_before_network(self):
        h=HTTP()
        with self.assertRaises(a.Problem):
            a.read_single_article(self.root,'https://example.com/s/x',h)
        self.assertEqual(h.calls,[])


if __name__=='__main__': unittest.main()
