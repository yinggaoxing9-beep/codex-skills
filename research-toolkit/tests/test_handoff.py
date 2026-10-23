import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("handoff", Path(__file__).parents[1] / "scripts/validate_handoff.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = "2026-01-02T10:00:00Z"


def ref(name):
    return {"id": name, "version": "1", "sha256": "a"*64, "reference": name+".json",
            "available_at": "2026-01-02T09:00:00Z"}


def artifact(kind="idea"):
    return {"schema_version": "research-handoff/1", "id": "synthetic-"+kind, "version": "1.0.0",
            "kind": kind, "as_of": NOW, "available_at": "2026-01-02T09:00:00Z",
            "created_at": NOW, "research_mode": "prospective", "valid_until": "2026-01-03T10:00:00Z",
            "producer": {"skill": "test-only", "sha256": "b"*64},
            "versions": {"data": None, "code": None, "model": None},
            "scope": {"entities": ["SYNTHETIC"], "target": "return_after_horizon",
                      "horizon_trading_days": None, "conditions": [], "use": "return"},
            "status": "candidate", "eligibility": "research", "evidence": [], "counterevidence": [],
            "upstream": [], "gaps": [], "payload": {"freshness_basis": "one-day window for this synthetic test"}}


def probability():
    a = artifact("probability")
    a.update(status="valid", eligibility="shadow", evidence=[ref(n) for n in ("validation","calibration","model","dependency")])
    a["scope"]["horizon_trading_days"] = 5
    a["versions"] = {"data": "data1", "code": "code1", "model": "model1"}
    a["payload"].update(probabilities={"up": .6, "down": .4}, inputs_complete=True, conditions_checked=True,
                         validation_ref="validation", calibration_ref="calibration", model_ref="model",
                         dependency_review_ref="dependency", semantics="binary_return", thresholds={"split":0},
                         label_rule="down:r<=split;up:r>split", label_version="label1", factor_set_sha256="c"*64)
    p = a["payload"]
    p["calibration"] = {"method": "identity_validated", "horizon_trading_days": 5,
                        "target": a["scope"]["target"], "model_version": "model1",
                        "entities": ["SYNTHETIC"], "conditions": [],
                        **{k: copy.deepcopy(p[k]) for k in ("factor_set_sha256","label_version","label_rule","thresholds","semantics")}}
    return a


class HandoffTests(unittest.TestCase):
    def check(self, a, **kw):
        return m.validate(a, at=NOW, **kw)

    def test_raw_idea_needs_no_invented_formula_or_period(self):
        self.assertEqual(self.check(artifact()), [])

    def test_unknown_probability_preserves_null(self):
        a = artifact("probability")
        a.update(status="unknown", gaps=["no validated combination"])
        a["payload"]["probabilities"] = None
        self.assertEqual(self.check(a), [])
        a["payload"]["probabilities"] = {"up":0,"down":0}
        self.assertTrue(self.check(a))

    def test_unknown_needs_reason(self):
        a = artifact()
        a["status"]="unknown"
        self.assertTrue(self.check(a))

    def test_valid_probability_and_zero_endpoint(self):
        a = probability()
        self.assertEqual(self.check(a, purpose="shadow", entity="SYNTHETIC", horizon=5), [])
        a["payload"]["probabilities"]={"up":0,"down":1}
        self.assertEqual(self.check(a, purpose="shadow",entity="SYNTHETIC",horizon=5), [])

    def test_rank_votes_and_uncalibrated_none_rejected(self):
        for method in ("rank","llm_vote","none"):
            with self.subTest(method=method):
                a=probability()
                a["payload"]["calibration"]["method"]=method
                self.assertTrue(self.check(a))

    def test_model_label_scope_and_factor_set_bound(self):
        for field, value in (("model_version","changed"),("horizon_trading_days",20),
                             ("label_version","changed"),("factor_set_sha256","d"*64),
                             ("thresholds",{"split":.1}),("entities",["OTHER"]),("conditions",["new"])):
            with self.subTest(field=field):
                a=probability()
                a["payload"]["calibration"][field]=value
                self.assertTrue(self.check(a))

    def test_no_unresolved_or_counterevidence_only_validation(self):
        a=probability()
        a["counterevidence"]=[a["evidence"].pop(0)]
        self.assertTrue(self.check(a))
        a=probability()
        a["payload"]["dependency_review_ref"]="unavailable"
        self.assertTrue(self.check(a))

    def test_nonfinite_out_of_range_bool_and_bad_sum(self):
        for values in ({"up":.7,"down":.7}, {"up":-1,"down":2}, {"up":True,"down":0},
                       {"up":float("nan"),"down":.4}, {"up":"0.6","down":.4}):
            a=probability()
            a["payload"]["probabilities"]=values
            self.assertTrue(self.check(a))

    def test_missing_inputs_and_unchecked_conditions(self):
        for field in ("inputs_complete","conditions_checked"):
            a=probability()
            a["payload"][field]=False
            self.assertTrue(self.check(a))
        a=probability()
        a["gaps"]=["missing factor"]
        self.assertTrue(self.check(a))

    def test_exclusive_and_independent_semantics(self):
        a=probability()
        p=a["payload"]
        p.update(semantics="ternary_return",probabilities={"up":.5,"down":.3,"neutral":.2},
                 thresholds={"lower":-.01,"upper":.01},
                 label_rule="down:r<lower;neutral:lower<=r<=upper;up:r>upper")
        for k in ("semantics","thresholds","label_rule"): p["calibration"][k]=copy.deepcopy(p[k])
        self.assertEqual(self.check(a),[])
        p["thresholds"]={"lower":.1,"upper":-.1}
        p["calibration"]["thresholds"]=p["thresholds"]
        self.assertTrue(self.check(a))
        a=probability()
        p=a["payload"]
        p.update(semantics="independent_events", probabilities={"drawdown":.8,"rebound":.8},
                 event_definitions={"drawdown":"any intraperiod drawdown beyond bound","rebound":"close above entry"})
        p["calibration"]["semantics"]="independent_events"
        p["calibration"]["event_definitions"]=copy.deepcopy(p["event_definitions"])
        self.assertEqual(self.check(a),[])
        p["event_definitions"]["drawdown"]="a materially changed event"
        self.assertTrue(any("event definitions mismatch" in e for e in self.check(a)))

    def test_future_reference_and_expired_artifact(self):
        a=artifact()
        a["evidence"]=[ref("future")]
        a["evidence"][0]["available_at"]="2026-01-02T11:00:00Z"
        self.assertTrue(self.check(a))
        a=artifact()
        a["valid_until"]=NOW
        self.assertTrue(self.check(a))

    def test_retrospective_does_not_claim_artifact_existed(self):
        a=artifact()
        a["created_at"]="2026-01-02T11:00:00Z"
        self.assertTrue(m.validate(a,at="2026-01-02T12:00:00Z"))
        a["research_mode"]="retrospective"
        self.assertEqual(m.validate(a,at="2026-01-02T12:00:00Z"),[])

    def test_timezone_required_and_equivalent_offsets(self):
        a=artifact()
        a["as_of"]="2026-01-02T18:00:00+08:00"
        self.assertEqual(self.check(a),[])
        a["as_of"]="2026-01-02T10:00:00"
        self.assertTrue(self.check(a))

    def test_scope_and_qualification(self):
        a=probability()
        self.assertTrue(self.check(a,purpose="production"))
        self.assertTrue(self.check(a,entity="OTHER"))
        self.assertTrue(self.check(a,horizon=20))
        a["status"]="suspended"
        a["payload"]["probabilities"]=None
        self.assertTrue(self.check(a,purpose="shadow"))

    def test_factor_candidate_and_native_approval(self):
        a=artifact("factor")
        a["scope"]["horizon_trading_days"]=5
        a["payload"].update(formal_name="Alpha_5Day_test_factor",lookback_trading_days=20,definition="test-only formula")
        self.assertEqual(self.check(a),[])
        a["status"]="valid"; a["eligibility"]="production"
        self.assertTrue(self.check(a,purpose="production"))
        a["versions"].update(data="d1",code="c1")
        a["evidence"]=[ref("approval")]
        a["payload"].update(registry_ref="native-id@1",registry_state="ACTIVE",approval_ref="approval",conditions_checked=True,inputs_complete=True)
        self.assertEqual(self.check(a,purpose="production",entity="SYNTHETIC",horizon=5),[])
        a["payload"]["registry_state"]="SUSPENDED"
        self.assertTrue(self.check(a,purpose="production"))
        a["payload"]["formal_name"]="Alpha_20Day_test_factor"
        self.assertTrue(self.check(a))

    def test_reference_identity_and_immutable_version(self):
        a=artifact()
        a["evidence"]=[ref("one"),dict(ref("one"),version="2")]
        self.assertTrue(self.check(a))
        a=artifact(); old=copy.deepcopy(a)
        a["payload"]["new"]="changed"
        self.assertTrue(self.check(a,prior=old))
        a["version"]="1.0.1"
        self.assertEqual(self.check(a,prior=old),[])

    def test_malformed_shape_and_no_extra_top_fields(self):
        for a in ([],{},dict(artifact(),surprise=True),dict(artifact(),evidence="wrong")):
            self.assertTrue(self.check(a))
        a=artifact(); a["scope"]["horizon_trading_days"]=True
        self.assertTrue(self.check(a))

    def test_local_payload_hash_and_no_escape(self):
        with tempfile.TemporaryDirectory(prefix="handoff-test-") as folder:
            root=Path(folder).resolve()
            assert root.parent==Path(tempfile.gettempdir()).resolve()
            p=root/"input.json"; p.write_bytes(b'{"synthetic":true}')
            r=dict(ref("input"),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            a=artifact("research_summary"); a["upstream"]=[r]
            self.assertEqual(self.check(a,reference_root=root),[])
            p.write_bytes(b'{"synthetic":false}')
            self.assertTrue(self.check(a,reference_root=root))
            r["reference"]="../outside.json"
            self.assertTrue(self.check(a,reference_root=root))

    def test_reference_cannot_arrive_after_aggregate_available_time(self):
        a=artifact()
        a["evidence"]=[ref("late")]
        a["evidence"][0]["available_at"]="2026-01-02T09:30:00Z"
        self.assertTrue(self.check(a))

    def test_qualified_consumption_requires_explicit_target(self):
        self.assertTrue(self.check(probability(),purpose="shadow"))

    def test_nonfinite_arbitrary_payload_fails_closed(self):
        a=artifact(); a["payload"]["unknown"]=float("nan")
        self.assertTrue(self.check(a))

    def test_new_schema_keywords_fail_closed(self):
        schema={"type":"string","unimplementedRule":True}
        self.assertTrue(m.shape_errors("value",schema,schema))


if __name__=="__main__":
    unittest.main()
