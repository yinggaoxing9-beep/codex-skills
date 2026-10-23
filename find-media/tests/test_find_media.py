"""Offline contracts + actual FFmpeg tests on generated, redistributable fixtures."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import ffmpeg_path, run
import contract
import media
import subtitles
import trace_search as trace

def report(status="unresolved"):
    return {"schema_version":1, "task_type":"anime", "inputs":[], "process":[], "coverage":{},
            "unresolved":[], "next_steps":[], "segments":[{
                "id":"s1", "input_range":[0,4], "status":status, "work":{"name":"Synthetic A"},
                "confirmation":dict.fromkeys(("title","episode","time"),"unverified"),
                "evidence":[], "confirmation_evidence":{}}]}

def confirmed_segment():
    seg = report()["segments"][0]
    seg.update(status="verified_anchor", evidence=[{
        "id":"e1","source":"synthetic-source","checked_at":"2026-10-21","observation":"compared generated frame"}],
        confirmation={"title":"confirmed","episode":"unverified","time":"confirmed"},
        confirmation_evidence={"title":["e1"],"time":["e1"]},
        anchors=[{"input_time":1,"source_time":10,"evidence_id":"e1","reviewed":True}],
        time_basis={"version":"synthetic-v1","clock":"source decoded seconds","precision":"1s sample","error":None})
    return seg

class SubtitleTests(unittest.TestCase):
    def test_srt_repeat_version_unknown(self):
        with tempfile.TemporaryDirectory(prefix="find-media-") as folder:
            p=Path(folder)/"repeated.srt"
            p.write_text("1\n00:00:02,000 --> 00:00:03,000\nHello, traveler!\n\n2\n00:01:02,500 --> 00:01:03,000\nHello traveler\n",encoding="utf-8")
            result=subtitles.search(p,"hello traveler")
            self.assertEqual([r["start"] for r in result["matches"]],[2,62.5])
            self.assertIsNone(result["time_basis"]["version"])
            self.assertIsNone(result["time_basis"]["offset_to_video"])
    def test_ass_commas_and_tags(self):
        data="[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:01:02.50,0:01:04.00,Default,,0,0,0,,{\\i1}Hello, traveler!\\NAgain"
        row=list(subtitles.parse(data,".ass"))[0]
        self.assertEqual(row["start"],62.5)
        self.assertEqual(row["text"],"Hello, traveler! Again")
    def test_vtt_settings_and_no_match(self):
        rows=list(subtitles.parse("WEBVTT\n\n00:02.000 --> 00:03.000 align:start\n<v A>Hi</v>\n",".vtt"))
        self.assertEqual(rows,[{"start":2.0,"end":3.0,"text":"Hi"}])

class ProviderTests(unittest.TestCase):
    def test_parse_types_and_low_score(self):
        rows=trace.candidates({"result":[{"anilist":12,"episode":None,"similarity":.4},
            {"anilist":{"id":13,"title":{"english":"English"}}, "episode":"01-02","from":2,"to":4,"at":3,"similarity":.99}]})
        self.assertEqual(rows[0]["retrieval_hint"],"low_similarity")
        self.assertEqual(rows[1]["episode"],"01-02")
        self.assertEqual(rows[1]["provider_anchor"],3)
        self.assertEqual(rows[1]["provider_scene"],[2,4])
        self.assertTrue(all(r["confirmation"]["time"]=="unverified" for r in rows))
    def test_failure_not_no_match(self):
        self.assertEqual(trace.classify(402,{"error":"Concurrency"}),"quota_or_concurrency")
        self.assertEqual(trace.classify(403,{}),"credentials_error")
        self.assertEqual(trace.classify(0,{"error":"network_or_timeout"}),"network_or_timeout")
        self.assertEqual(trace.classify(200,{"result":[]}),"no_match")
    def call_search(self, replies, images=2, budget=3, retries=1):
        folder=tempfile.TemporaryDirectory(prefix="find-media-")
        self.addCleanup(folder.cleanup)
        paths=[]
        for i in range(images):
            p=Path(folder.name)/f"im-{i}.bin"; p.write_bytes(bytes([i])); paths.append(str(p))
        queue=iter(replies)
        calls=[]
        def request(url,payload=None,timeout=30):
            calls.append((url,payload))
            return next(queue)
        vector_result=type("P",(),{"stdout":json.dumps({"vector":list(range(33))}).encode()})()
        with patch.object(trace,"run",return_value=vector_result):
            result=trace.search(paths,Path(folder.name)/"cache",budget,retries,
                                request_fn=request,sleep_fn=lambda _:None)
        return result,calls
    def test_402_stops_queue(self):
        r,c=self.call_search([(200,{"quota":100,"quotaUsed":0},{}),(402,{"error":"quota"},{})])
        self.assertEqual(r["search_attempts"],1)
        self.assertEqual([f["process_status"] for f in r["frames"]],["quota_or_concurrency","stopped_after_402"])
    def test_retry_consumes_budget(self):
        r,c=self.call_search([(200,{},{}),(503,{},{}),(429,{},{"retry-after":"999"})],budget=2,retries=2)
        self.assertEqual(r["search_attempts"],2)
        self.assertEqual(r["frames"][1]["process_status"],"budget_exhausted")
    def test_cache_no_match_and_vector_payload(self):
        r,c=self.call_search([(200,{},{}),(200,{"result":[]},{})])
        self.assertEqual(r["search_attempts"],1)
        self.assertTrue(r["frames"][1]["cache_hit"])
        self.assertEqual(set(c[1][1]),{"vector"})
    def test_timeout_not_candidate_rejection(self):
        r,c=self.call_search([(200,{},{}),(0,{"error":"network_or_timeout"},{})],images=1)
        self.assertEqual(r["frames"][0]["process_status"],"network_or_timeout")
        self.assertEqual(r["frames"][0]["candidates"],[])
    def test_known_quota_depleted_skips_search(self):
        r,c=self.call_search([(200,{"quota":2,"quotaUsed":2,"id":"private-ip"},{})],images=2)
        self.assertEqual(r["search_attempts"],0)
        self.assertEqual([f["process_status"] for f in r["frames"]],["quota_exhausted"]*2)
        self.assertNotIn("id",r["quota_check"]["raw"])
    def test_request_timeout_handled(self):
        with patch("urllib.request.urlopen",side_effect=TimeoutError):
            self.assertEqual(trace.request_json("https://api.trace.moe/me")[0],0)

class ContractTests(unittest.TestCase):
    def test_no_threshold_promotion(self):
        r=report("title_only")
        self.assertTrue(contract.validate(r))
    def test_live_action_title_only(self):
        r=report("title_only"); r["task_type"]="live_action"
        s=r["segments"][0]; s["confirmation"]["title"]="confirmed"
        s["evidence"]=[{"id":"official","source":"https://example.org/film","checked_at":"2026-10-21","observation":"Distinctive plot matches"}]
        s["confirmation_evidence"]={"title":["official"]}
        self.assertEqual(contract.validate(r),[])
        self.assertNotIn("anchors",s)
    def test_speed_change_no_interval_extrapolation(self):
        r=report(); r["segments"][0]=confirmed_segment()
        self.assertEqual(contract.validate(r),[])
        r["segments"][0]["status"]="verified_interval"
        r["segments"][0]["source_interval"]=[10,14]
        self.assertTrue(contract.validate(r))
    def test_two_anchors_still_require_continuity(self):
        r=report(); s=confirmed_segment(); r["segments"][0]=s
        s.update(status="verified_interval",source_interval=[10,12])
        s["anchors"].append({"input_time":3,"source_time":12,"evidence_id":"e1","reviewed":True})
        self.assertTrue(contract.validate(r))
        s["continuity"]={"reviewed_source_span":True,"evidence_id":"e1"}
        self.assertEqual(contract.validate(r),[])
    def test_multisource_never_merge(self):
        r=report(); a=confirmed_segment(); b=copy.deepcopy(a)
        b.update(id="s2",input_range=[4,8],work={"name":"Synthetic B"})
        b["anchors"][0]["input_time"]=5
        r["segments"]=[a,b]
        self.assertEqual(contract.validate(r),[])
        self.assertEqual([s["work"]["name"] for s in r["segments"]],["Synthetic A","Synthetic B"])
    def test_game_exclusion_reason(self):
        r=report(); r["task_type"]="game"; r["segments"][0]["excluded"]=True
        self.assertTrue(contract.validate(r))
        r["segments"][0]["exclusion_reason"]="User says screen/UI differs"
        self.assertEqual(contract.validate(r),[])

class ActualMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try: cls.ff=ffmpeg_path()
        except ValueError: raise unittest.SkipTest("FFmpeg not installed")
        cls.temp=tempfile.TemporaryDirectory(prefix="find-media-video-")
        cls.root=Path(cls.temp.name)
        cls.cut=cls.root/"cut.mp4"
        run([cls.ff,"-v","error","-f","lavfi","-i","testsrc2=size=320x240:rate=10:duration=3",
             "-f","lavfi","-i","testsrc=size=320x240:rate=10:duration=3",
             "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
             "-map","[v]","-c:v","libx264","-n",cls.cut])
        cls.single=cls.root/"single.mp4"
        run([cls.ff,"-v","error","-f","lavfi","-i","testsrc2=size=320x240:rate=10:duration=6",
             "-c:v","libx264","-pix_fmt","yuv420p","-n",cls.single])
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def test_cut_and_no_cut(self):
        cut=media.prepare(self.cut,self.root/"frames-cut",threshold=.25,ffmpeg=self.ff)
        single=media.prepare(self.single,self.root/"frames-single",threshold=.99,ffmpeg=self.ff)
        self.assertGreaterEqual(cut["scene_count"],2)
        self.assertEqual(single["scene_count"],1)
        self.assertGreaterEqual(single["selected_count"],2)
        self.assertEqual(cut["lookup_coverage"]["queried_frame_ids"],[])
    def test_nonzero_start_timing(self):
        r=media.prepare(self.cut,self.root/"seek",start=2,max_duration=3,threshold=.25,ffmpeg=self.ff)
        boundaries=[s["input_range"][0] for s in r["scenes"]]
        self.assertTrue(any(abs(t-3)<.11 for t in boundaries),boundaries)
        self.assertEqual(r["analyzed_input_range"],[2,5])
    def test_budgets_unprocessed(self):
        r=media.prepare(self.cut,self.root/"budget",max_frames=1,ffmpeg=self.ff)
        self.assertEqual(r["attempted_frame_count"],1)
        self.assertTrue(any(s["status"]=="unprocessed" for s in r["scenes"]))
        self.assertEqual(r["stop_reason"],"frame_budget")
    def test_mirror_provenance_and_local_compare(self):
        original=self.root/"query.png"; media.extract(self.ff,self.single,2,original,30)
        mirror=self.root/"mirror.png"; restored=self.root/"restored.png"
        media.transform(original,mirror,mirror=True)
        media.transform(mirror,restored,mirror=True)
        self.assertEqual(media.distance(original,restored),0)
        self.assertTrue(Path(str(mirror)+".provenance.json").exists())
        r=media.compare(restored,self.single,self.root/"local-compare",0,4,step=1,ffmpeg=self.ff)
        self.assertEqual(r["candidates"][0]["source_time"],2)
        self.assertEqual(r["confirmation"],"unverified")

    def test_real_vector_unicode_path(self):
        p=self.root/"unicode 空格 路径.png"
        media.extract(self.ff,self.single,1,p,30)
        r=json.loads(run(["node",Path(trace.__file__).with_name("trace-vector.mjs"),p]).stdout)
        self.assertEqual(len(r["vector"]),33)
        self.assertTrue(all(isinstance(v,(int,float)) for v in r["vector"]))
    def test_two_sources_query_remains_per_frame(self):
        paths=[]
        for i,t in enumerate((1,4)):
            p=self.root/f"mixed-query-{i}.png"
            media.extract(self.ff,self.cut,t,p,30)
            paths.append(str(p))
        real_run=trace.run
        calls=[0]
        def response(url,payload=None,timeout=30):
            if url.endswith("/me"): return 200,{"quota":100,"quotaUsed":0},{}
            calls[0]+=1
            return 200,{"result":[{"anilist":calls[0],"episode":calls[0],"at":10*calls[0],"similarity":.99}]},{}
        result=trace.search(paths,self.root/"mixed-cache",budget=2,request_fn=response,sleep_fn=lambda _:None)
        self.assertEqual([f["candidates"][0]["work_id"]["id"] for f in result["frames"]],[1,2])
        self.assertTrue(all(f["candidates"][0]["confirmation"]["title"]=="unverified" for f in result["frames"]))

    def test_output_no_overwrite(self):
        p=self.root/"exists"; p.mkdir()
        with self.assertRaises(ValueError): media.prepare(self.single,p,ffmpeg=self.ff)


class ReviewRegressionTests(unittest.TestCase):
    def test_interval_outside_anchors_and_nan_rejected(self):
        r=report(); s=confirmed_segment(); r["segments"][0]=s
        s.update(status="verified_interval",source_interval=[10,20],
                 continuity={"reviewed_source_span":True,"evidence_id":"e1"})
        s["anchors"]=[{"input_time":1,"source_time":900,"evidence_id":"e1","reviewed":True},
                      {"input_time":2,"source_time":950,"evidence_id":"e1","reviewed":True}]
        self.assertTrue(contract.validate(r))
        s["source_interval"]=[float("nan"),float("nan")]
        s["anchors"][0]["source_time"]=float("nan")
        self.assertTrue(contract.validate(r))
    def test_truncated_http_is_process_failure(self):
        import http.client
        response=type("Response",(),{
            "__enter__":lambda self:self,
            "__exit__":lambda *args:None,
            "read":lambda *args:(_ for _ in ()).throw(http.client.IncompleteRead(b"x",8))})()
        with patch("urllib.request.urlopen",return_value=response):
            code,raw,_=trace.request_json("https://api.trace.moe/me")
        self.assertEqual(code,0)
        self.assertEqual(raw["error"],"network_or_timeout")
    def test_cache_available_when_quota_empty(self):
        with tempfile.TemporaryDirectory(prefix="find-media-") as folder:
            path=Path(folder)/"frame.png"; path.write_bytes(b"fixture")
            directory=Path(folder)/"cache"
            vector_result=type("P",(),{"stdout":json.dumps({"vector":list(range(33))}).encode()})()
            def first(url,payload=None,timeout=30):
                return (200,{"quota":5,"quotaUsed":0},{}) if url.endswith("/me") else (200,{"result":[]},{})
            def exhausted(url,payload=None,timeout=30):
                self.assertTrue(url.endswith("/me"),"cache should avoid search")
                return 200,{"quota":5,"quotaUsed":5},{}
            with patch.object(trace,"run",return_value=vector_result):
                trace.search([str(path)],directory,request_fn=first,sleep_fn=lambda _:None)
                result=trace.search([str(path)],directory,request_fn=exhausted,sleep_fn=lambda _:None)
            self.assertEqual(result["search_attempts"],0)
            self.assertEqual(result["process_status"],"ok")
            self.assertTrue(result["frames"][0]["cache_hit"])
    def test_cli_all_failed_writes_report_then_exit2(self):
        import find_media as cli
        with tempfile.TemporaryDirectory(prefix="find-media-") as folder:
            output=Path(folder)/"failed.json"
            response={"process_status":"failed","search_attempts":1,
                      "frames":[{"input":{"path":"synthetic"},"process_status":"rate_or_service_limited","candidates":[]}]}
            with patch.object(sys,"argv",["find_media.py","trace","synthetic","--out",str(output),"--cache",str(Path(folder)/"cache")]), patch.object(trace,"search",return_value=response), patch("sys.stdout",new=io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli.main()
            self.assertEqual(raised.exception.code,2)
            self.assertEqual(json.loads(output.read_text())["process_status"],"failed")
    def test_multi_segment_report_keeps_table_contiguous(self):
        r=report(); r["segments"].append(copy.deepcopy(r["segments"][0]))
        text=contract.render(r)
        first_detail=text.index("\ns1：")
        self.assertEqual(text[:first_detail].count("| Synthetic A |"),2)


class FinalReviewRegressionTests(unittest.TestCase):
    def test_verified_anchor_input_outside_range_rejected(self):
        r=report(); s=confirmed_segment(); r["segments"][0]=s
        s["input_range"]=[0,2]; s["anchors"][0]["input_time"]=99
        self.assertTrue(contract.validate(r))
    def test_http_error_body_truncated_preserves_http_status(self):
        import http.client
        import urllib.error
        error=urllib.error.HTTPError("https://api.trace.moe/search",503,"busy",{},None)
        error.read=lambda *args: (_ for _ in ()).throw(http.client.IncompleteRead(b"x",8))
        with patch("urllib.request.urlopen",side_effect=error):
            code,raw,_=trace.request_json("https://api.trace.moe/search")
        self.assertEqual(code,503)
        self.assertEqual(raw["error"],"unreadable_http_error_body")

if __name__=="__main__":
    unittest.main()
