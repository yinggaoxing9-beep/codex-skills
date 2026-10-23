"""Synthetic cross-workflow demonstration; outputs are not financial evidence."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(source, output):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError("output must be outside the source checkout")
    release = load(source / "scripts/skill_release.py", "demo_release")
    contract = load(source / "research-toolkit/scripts/validate_handoff.py", "demo_contract")
    intake = load(source / "fundamental-signal-intake/scripts/validate_ledger.py", "demo_intake")
    original = source / "evidence-driven-valuation/example/synthetic-handoff.json"
    native = json.loads(original.read_text(encoding="utf-8"))
    if intake.validate(native["ledger"]):
        raise ValueError("existing native ledger fixture failed its validator")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(original, output / "valuation-v2.json")
    paper = {"schema_version": "1.0", "operation": "search", "query": "synthetic offline fixture",
             "fetched_at": "2026-01-02T12:00:00Z", "records": [],
             "warnings": ["synthetic: no retrieved or verified papers"]}
    (output / "papers-v1.json").write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
    created = datetime.now(timezone.utc)
    at = created.isoformat()
    produced_by = {"skill": "research-toolkit", "sha256": release.digest(source / "research-toolkit")}
    def wrapper(name, kind, filename, payload):
        reference = {"id": filename, "version": "1", "sha256": hashlib.sha256((output / filename).read_bytes()).hexdigest(),
                     "reference": filename, "available_at": "2026-01-02T12:00:00Z"}
        return {"schema_version": "research-handoff/1", "id": name, "version": "1.0.0", "kind": kind,
                "as_of": "2026-01-02T12:00:00Z", "available_at": "2026-01-02T12:00:00Z",
                "created_at": at, "research_mode": "retrospective", "valid_until": (created + timedelta(minutes=30)).isoformat(),
                "producer": produced_by, "versions": {"data": reference["sha256"], "code": release.digest(Path(__file__)), "model": None},
                "scope": {"entities": ["SYNTHETIC"], "target": "offline contract demonstration", "horizon_trading_days": None, "conditions": ["synthetic only"], "use": "evidence"},
                "status": "unknown", "eligibility": "research", "evidence": [], "counterevidence": [],
                "gaps": ["synthetic fixture, not independently verified real evidence"],
                "upstream": [reference], "payload": dict(payload, freshness_basis="30-minute validity solely for a reproducible synthetic demo")}
    financial = wrapper("synthetic-financial-handoff", "valuation", "valuation-v2.json", {"native": native})
    research = wrapper("synthetic-literature-handoff", "research_summary", "papers-v1.json", {"native": paper})
    for name, artifact in (("financial-handoff.json", financial), ("research-handoff.json", research)):
        errors = contract.validate(artifact, at=at, reference_root=output)
        if errors:
            raise ValueError(errors)
        (output / name).write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"at": at, "producer": produced_by, "files": ["financial-handoff.json", "research-handoff.json"],
              "native_ledger": "pass", "handoff": "pass", "limits": ["synthetic engineering demonstration; no real source verification or investment result"]}
    (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(build(args.source_root, args.output), ensure_ascii=False, indent=2))
