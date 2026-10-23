import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import archive as a
import download_list as d
from test_archive import HTTP

URL='https://mp.weixin.qq.com/s?__biz=account&mid=1&idx=1&sn=s&chksm=checksum&scene=21#rd'


class PublicDownloadTests(unittest.TestCase):
    def test_request_keeps_checksum_canonical_deduplicates(self):
        self.assertIn('chksm=checksum',a.request_url(URL))
        self.assertNotIn('chksm',a.canonical(URL))
        self.assertEqual(a.canonical(URL),a.canonical(URL.replace('checksum','other')))
        self.assertTrue(a.request_url(URL.replace('https:', 'http:')).startswith('https:'))
        for value in ('https://mp.weixin.qq.com.evil/s/a','https://user@mp.weixin.qq.com/s/a','https://mp.weixin.qq.com:444/s/a'):
            with self.assertRaises(a.Problem): a.request_url(value)

    def test_single_refresh_uses_new_original_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=HTTP()
            a.read_single_article(Path(tmp),a.canonical(URL),h)
            result=a.read_single_article(Path(tmp),URL,h,refresh_days=0)
            self.assertEqual(h.calls[-1],a.request_url(URL))
            self.assertEqual(result['status'],'ok')

    def test_captcha_redirect_is_classified_without_retry(self):
        h=a.HTTP(interval=0,retries=2)
        e=urllib.error.HTTPError(URL,302,'Found',{'Location':'/mp/wappoc_appmsgcaptcha?token=hidden'},io.BytesIO())
        with patch.object(h.opener,'open',side_effect=e) as opened:
            with self.assertRaises(a.Problem) as caught: h.get(URL)
        self.assertEqual(caught.exception.code,'captcha_required')
        self.assertEqual(opened.call_count,1)
        self.assertNotIn('hidden',str(caught.exception))

    def test_all_records_registered_before_body_work_and_cache_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=a.Store(tmp)
            try:
                records=[{'url':URL,'title':'one'},{'url':URL.replace('mid=1','mid=2'),'title':'two'}]
                r=d.ingest_list(store,records,'account','Account')
                self.assertEqual((r['discovered'],r['body_missing']),(2,2))
                self.assertIsNone(r['directory']['reported_total'])
                h=HTTP()
                r=d.download(store,h,max_articles=1)
                self.assertEqual((r['body_success'],r['body_missing']),(1,1))
                d.ingest_list(store,records,'account','Account')
                r=d.download(store,h)
                self.assertEqual(len(h.calls),2)
                self.assertTrue(r['body_complete_for_discovered'])
                self.assertFalse(r['all_complete'])
                self.assertTrue(all('chksm=checksum' in url for url in h.calls))
            finally: store.close()

    def test_wrong_account_list_is_not_partially_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=a.Store(tmp)
            try:
                with self.assertRaises(a.Problem):
                    d.ingest_list(store,[{'url':URL},{'url':URL.replace('__biz=account','__biz=other')}],'account','Account')
                self.assertEqual(store.db.execute('SELECT count(*) FROM articles').fetchone()[0],0)
            finally: store.close()

    def test_access_failure_budget_preserves_pending_records(self):
        class Blocked:
            def __init__(self): self.calls=0
            def get(self,url):
                self.calls+=1
                raise a.Problem('captcha_required')
        with tempfile.TemporaryDirectory() as tmp:
            store=a.Store(tmp)
            try:
                d.ingest_list(store,[{'url':URL.replace('mid=1','mid='+str(i))} for i in range(5)],'account','Account')
                h=Blocked()
                r=d.download(store,h)
                self.assertEqual(h.calls,3)
                self.assertEqual(r['body_missing'],5)
                self.assertEqual(r['public_catalog']['stop_reason'],'consecutive_access_failures')
            finally: store.close()


    def test_portable_export_keeps_local_media_and_escapes_markup(self):
        import export_archive as e
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            store=a.Store(Path(tmp)/'archive')
            try:
                d.ingest_list(store,[{'url':URL,'title':'one'}],'account','Account')
                d.download(store,HTTP(),with_media=True)
                result=e.export(store.root,Path(tmp)/'offline')
                manifest=json.loads((Path(result['path'])/'manifest.json').read_text(encoding='utf8'))
                self.assertEqual(result['body_success'],1)
                self.assertEqual(result['unique_images'],1)
                article=Path(result['path'])/manifest['articles'][0]['html']
                rendered=article.read_text(encoding='utf8')
                self.assertIn('../media/',rendered)
                self.assertNotIn('ASSET_',rendered)
                md=(Path(result['path'])/manifest['articles'][0]['markdown']).read_text(encoding='utf8')
                self.assertNotIn('ASSET_',md)
                with zipfile.ZipFile(result['zip']) as z:
                    self.assertIsNone(z.testzip())
                    self.assertEqual(len([n for n in z.namelist() if '/media/' in n]),1)
                with self.assertRaises(a.Problem):e.export(store.root,Path(tmp)/'offline')
            finally:store.close()

if __name__=='__main__': unittest.main()
