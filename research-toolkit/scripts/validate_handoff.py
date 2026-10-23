"""Validate a handoff wrapper; preserve existing payload schemas and IDs.

Uses the standard library and this repository's fixed schema subset. Does not register factors, infer permissions, retrieve data,
fit models, execute payloads, or authenticate evidence claims.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re


SCHEMA = Path(__file__).resolve().parents[1] / "references" / "handoff.schema.json"


def instant(value):
    if not isinstance(value, str) or "T" not in value.upper():
        raise ValueError("ISO date-time required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def shape_errors(value, schema, root_schema, path=""):
    """Only the documented, tested keywords in handoff.schema.json are supported."""
    allowed = {"$schema", "$defs", "title", "description", "$ref", "type", "properties",
               "additionalProperties", "required", "items", "minItems", "uniqueItems",
               "minLength", "minimum", "pattern", "enum", "const", "format"}
    unsupported = set(schema) - allowed
    if unsupported:
        return [f"{path}: unsupported schema keywords {sorted(unsupported)}"]
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/") or ref[8:] not in root_schema["$defs"]:
            return [f"{path}: unsupported schema ref"]
        return shape_errors(value, root_schema["$defs"][ref[8:]], root_schema, path)
    errors = []
    types = schema.get("type")
    types = [types] if isinstance(types, str) else types
    checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
              "string": lambda x: isinstance(x, str), "null": lambda x: x is None,
              "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
              "number": lambda x: isinstance(x, (int,float)) and not isinstance(x,bool) and math.isfinite(x),
              "boolean": lambda x: isinstance(x, bool)}
    if types and not any(t in checks and checks[t](value) for t in types):
        return [f"{path}: expected {types}"]
    for keyword in ("enum", "const"):
        choices = schema.get(keyword) if keyword == "enum" else [schema.get(keyword)]
        if keyword in schema and value not in choices:
            errors.append(f"{path}: invalid {keyword}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: empty/short string")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: pattern mismatch")
        if schema.get("format") == "date-time":
            try:
                instant(value)
            except (ValueError, TypeError):
                errors.append(f"{path}: timezone-aware ISO date-time required")
    if isinstance(value, (int,float)) and not isinstance(value, bool):
        if not math.isfinite(value) or ("minimum" in schema and value < schema["minimum"]):
            errors.append(f"{path}: invalid numeric bound")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}/{key}: missing")
        if schema.get("additionalProperties") is False:
            errors += [f"{path}/{k}: unknown field" for k in value if k not in props]
        for key, child in props.items():
            if key in value:
                errors.extend(shape_errors(value[key], child, root_schema, f"{path}/{key}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if schema.get("uniqueItems") and len({canonical_hash(x) for x in value}) != len(value):
            errors.append(f"{path}: duplicate items")
        for i, child in enumerate(value):
            if "items" in schema:
                errors.extend(shape_errors(child, schema["items"], root_schema, f"{path}/{i}"))
    return errors


def verify_local_refs(refs, root):
    root = Path(root).absolute()
    errors = []
    if any(x.is_symlink() or getattr(x, "is_junction", lambda: False)() for x in [root, *root.parents]):
        return ["reference root has a linked ancestor"]
    root = root.resolve()
    for ref in refs:
        relative = Path(ref["reference"])
        path = root / relative
        if relative.is_absolute() or not path.resolve().is_relative_to(root):
            errors.append(f"reference outside root: {ref['id']}")
            continue
        if any(x.is_symlink() or getattr(x, "is_junction", lambda: False)()
               for x in [path, *path.parents] if x != root and x.is_relative_to(root)):
            errors.append(f"linked reference: {ref['id']}")
            continue
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != ref["sha256"]:
                errors.append(f"reference changed: {ref['id']}")
        except OSError:
            errors.append(f"reference missing/unreadable: {ref['id']}")
    return errors


def validate(data, *, at, purpose="research", entity=None, horizon=None, prior=None, reference_root=None):
    try:
        canonical_hash(data)
    except (ValueError, TypeError):
        return ["artifact must be finite JSON"]
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = shape_errors(data, schema, schema)
    if errors:
        return sorted(errors)
    def need(condition, reason):
        if not condition:
            errors.append(reason)
    try:
        cutoff, available, expiry, use_at = map(instant, (data["as_of"], data["available_at"], data["valid_until"], at))
        need(available <= cutoff <= use_at < expiry, "PIT/freshness: available_at <= as_of <= consumption time < valid_until required")
        created = instant(data["created_at"])
        need(available <= created <= use_at, "created_at must be after inputs and no later than consumption")
        if data["research_mode"] == "prospective":
            need(created <= cutoff, "prospective artifact must already exist at decision cutoff")
        need(isinstance(data["payload"].get("freshness_basis"), str) and bool(data["payload"]["freshness_basis"].strip()), "explicit freshness basis required")
        refs = data["evidence"] + data["counterevidence"] + data["upstream"]
        if reference_root is not None:
            errors.extend(verify_local_refs(refs, reference_root))
        identities = {}
        id_versions = {}
        for r in refs:
            need(instant(r["available_at"]) <= available, f"PIT: reference available after aggregate available_at {r['id']}")
            key = (r["id"], r["version"])
            need(key not in identities or identities[key] == r["sha256"], f"conflicting immutable reference: {key}")
            identities[key] = r["sha256"]
            need(r["id"] not in id_versions or id_versions[r["id"]] == (r["version"], r["sha256"]),
                 f"ambiguous unversioned reference ID: {r['id']}")
            id_versions[r["id"]] = (r["version"], r["sha256"])
        if prior is not None:
            need((prior["id"], prior["version"]) != (data["id"], data["version"]) or canonical_hash(prior) == canonical_hash(data),
                 "same id/version has different content; append a new version")
        if data["status"] == "unknown":
            need(bool(data["gaps"]), "unknown needs reasons")
        if purpose not in {"research", "shadow", "production"}:
            errors.append("invalid consumption purpose")
        elif purpose != "research":
            need(data["status"] == "valid", "non-valid artifact cannot be consumed")
            allowed = {"shadow", "production"} if purpose == "shadow" else {"production"}
            need(data["eligibility"] in allowed, "qualification does not permit requested use")
            need(bool(data["evidence"]), "qualified use requires evidence")
        need(data["status"] not in {"suspended", "rejected", "expired"} or purpose == "research",
             "inactive artifact cannot be invoked")
        if entity is not None:
            need(entity in data["scope"]["entities"], "entity outside validated scope")
        if horizon is not None:
            need(horizon == data["scope"]["horizon_trading_days"], "horizon outside validated scope")
        p = data["payload"]
        if purpose != "research" and data["kind"] in {"factor", "probability"}:
            need(entity is not None and horizon is not None, "qualified consumption requires explicit entity and horizon")
        if data["kind"] == "factor":
            formal = p.get("formal_name")
            m = re.fullmatch(r"Alpha_([1-9][0-9]*)Day_[a-z][a-z0-9]*(?:_[a-z0-9]+)*", str(formal))
            need(m is not None, "formal factor name must be Alpha_<N>Day_<semantic_slug>")
            need(m is not None and int(m[1]) == data["scope"]["horizon_trading_days"], "factor name target horizon mismatch")
            need(isinstance(p.get("lookback_trading_days"), int) and not isinstance(p.get("lookback_trading_days"), bool) and p["lookback_trading_days"] > 0, "lookback must be separate and positive")
            need(bool(p.get("definition")), "formal factor requires definition")
            # These are references to independently verified native registry state.
            if purpose != "research":
                need(bool(p.get("registry_ref")), "qualified factor requires native registry reference")
                need(all(data["versions"][k] for k in ("data", "code")), "qualified factor requires data/code versions")
                need(p.get("registry_state") in ({"SHADOW", "ACTIVE"} if purpose == "shadow" else {"ACTIVE"}), "native registry state forbids use")
                need(p.get("approval_ref") in {r["id"] for r in data["evidence"]}, "independent approval evidence required; generator cannot approve")
                need(p.get("conditions_checked") is True and p.get("inputs_complete") is True and not data["gaps"], "factor applicability or inputs missing")
        if data["kind"] == "probability":
            probabilities = p.get("probabilities")
            if data["status"] != "valid":
                need(probabilities is None, "unknown/non-valid probability must be null, never zero or a score")
            else:
                need(all(data["versions"][k] for k in ("model", "data", "code")), "probability requires model/data/code versions")
                need(data["scope"]["horizon_trading_days"] is not None, "probability target horizon required")
                need(not data["gaps"] and p.get("inputs_complete") is True and p.get("conditions_checked") is True, "missing inputs/applicability must fail closed")
                need(data["eligibility"] in {"shadow", "production"}, "unvalidated research artifact cannot publish calibrated probabilities")
                refs_by_id = {r["id"]: r for r in data["evidence"] + data["upstream"]}
                calibration = p.get("calibration", {})
                need(isinstance(calibration, dict), "calibration object required")
                if not isinstance(calibration, dict):
                    calibration = {}
                need(calibration.get("method") in {"platt", "isotonic", "beta", "temperature", "empirical_frequency", "identity_validated"}, "unsupported/unvalidated calibration; rank/LLM votes/none are not calibration")
                for key in ("validation_ref", "calibration_ref", "model_ref", "dependency_review_ref"):
                    need(p.get(key) in refs_by_id, f"{key} must resolve to versioned evidence")
                need(calibration.get("horizon_trading_days") == data["scope"]["horizon_trading_days"], "calibration horizon mismatch")
                need(calibration.get("target") == data["scope"]["target"], "calibration label target mismatch")
                need(calibration.get("model_version") == data["versions"]["model"], "calibration model version mismatch")
                need(isinstance(p.get("factor_set_sha256"),str) and re.fullmatch(r"[a-f0-9]{64}",p["factor_set_sha256"]) is not None,
                     "factor set hash required")
                need(bool(p.get("label_version")), "label version required")
                for field in ("factor_set_sha256", "label_version", "label_rule", "thresholds", "semantics"):
                    need(field in p and calibration.get(field) == p[field], f"calibration {field} mismatch")
                need(calibration.get("entities") == data["scope"]["entities"] and
                     calibration.get("conditions") == data["scope"]["conditions"], "calibration scope mismatch")
                need(isinstance(probabilities, dict) and bool(probabilities), "probabilities object required")
                if isinstance(probabilities, dict):
                    need(all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in probabilities.values()), "probabilities must be finite numbers in [0,1]")
                    semantics = p.get("semantics")
                    if semantics == "ternary_return":
                        need(set(probabilities) == {"up", "down", "neutral"}, "ternary labels must be up/down/neutral")
                        t = p.get("thresholds", {})
                        lo, hi = t.get("lower"), t.get("upper")
                        need(all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in (lo, hi)) and lo <= hi, "finite lower <= upper thresholds required")
                        need(p.get("label_rule") == "down:r<lower;neutral:lower<=r<=upper;up:r>upper", "ternary return labels must partition outcomes")
                    elif semantics == "binary_return":
                        need(set(probabilities) == {"up", "down"}, "binary labels must be up/down")
                        t = p.get("thresholds", {}).get("split")
                        need(not isinstance(t, bool) and isinstance(t, (int, float)) and math.isfinite(t), "finite split threshold required")
                        need(p.get("label_rule") == "down:r<=split;up:r>split", "binary labels must partition outcomes")
                    elif semantics == "independent_events":
                        need(calibration.get("event_definitions") == p.get("event_definitions"), "calibration event definitions mismatch")
                        need(isinstance(p.get("event_definitions"), dict) and set(p["event_definitions"]) == set(probabilities) and all(isinstance(v,str) and v.strip() for v in p["event_definitions"].values()), "independent event definitions required")
                    else:
                        errors.append("explicit probability semantics required")
                    if semantics in {"ternary_return", "binary_return"}:
                        need(all(isinstance(v, (int, float)) for v in probabilities.values()) and abs(sum(probabilities.values()) - 1) <= 1e-8, "exclusive exhaustive probabilities must sum to one")
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        errors.append(f"malformed contract: {exc}")
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("artifact", type=Path)
    p.add_argument("--at", required=True, help="explicit timezone-aware consumption timestamp")
    p.add_argument("--purpose", choices=("research", "shadow", "production"), default="research")
    p.add_argument("--entity")
    p.add_argument("--horizon", type=int)
    p.add_argument("--prior", type=Path)
    p.add_argument("--reference-root", type=Path)
    args = p.parse_args()
    try:
        data = json.loads(args.artifact.read_text(encoding="utf-8-sig"))
        prior = json.loads(args.prior.read_text(encoding="utf-8-sig")) if args.prior else None
        errors = validate(data, at=args.at, purpose=args.purpose, entity=args.entity, horizon=args.horizon, prior=prior, reference_root=args.reference_root)
        print(json.dumps({"valid": not errors, "eligible_by_contract": not errors and data["status"] == "valid",
                          "refs_verified": args.reference_root is not None and not errors,
                          "execution_authorized": False,
                          "limits": ["contract checks do not authenticate evidence, registry state or model reliability"],
                          "status": data.get("status") if not errors else "unknown",
                          "errors": errors, "sha256": canonical_hash(data)}, ensure_ascii=False, indent=2))
        return 1 if errors else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "eligible_by_contract": False, "execution_authorized": False, "status": "unknown", "errors": [str(exc)]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
