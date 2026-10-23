"""Cross-task demo keeps native payloads and rejects stale/tampered references."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("handoff_demo", ROOT / "research-toolkit/example/handoff-demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
contract = demo.load(ROOT / "research-toolkit/scripts/validate_handoff.py", "demo_validator")


class DemoIntegrationTests(unittest.TestCase):
    def test_native_payload_and_qualifications_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "demo"
            receipt = demo.build(ROOT, out)
            native_path = ROOT / "evidence-driven-valuation/example/synthetic-handoff.json"
            self.assertEqual((out / "valuation-v2.json").read_bytes(), native_path.read_bytes())
            wrapper = json.loads((out / "financial-handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(wrapper["payload"]["native"], json.loads(native_path.read_text(encoding="utf-8")))
            self.assertEqual(wrapper["status"], "unknown")
            self.assertEqual(wrapper["eligibility"], "research")
            self.assertEqual(contract.validate(wrapper, at=receipt["at"], reference_root=out), [])

    def test_tampered_upstream_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "demo"
            receipt = demo.build(ROOT, out)
            wrapper = json.loads((out / "research-handoff.json").read_text(encoding="utf-8"))
            (out / "papers-v1.json").write_text('{"records":["changed"]}', encoding="utf-8")
            errors = contract.validate(wrapper, at=receipt["at"], reference_root=out)
            self.assertTrue(any("reference changed" in e for e in errors), errors)

    def test_expiry_is_not_renewed_by_consumption(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "demo"
            demo.build(ROOT, out)
            wrapper = json.loads((out / "research-handoff.json").read_text(encoding="utf-8"))
            errors = contract.validate(wrapper, at=wrapper["valid_until"], reference_root=out)
            self.assertTrue(any("PIT/freshness" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
