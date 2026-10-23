"""Serial vector-only trace.moe client; bounded attempts and task-local cache."""
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import socket
import time
import urllib.request
import urllib.error
from common import load, now, run, fingerprint, save_new

API = "https://api.trace.moe"

def request_json(url, payload=None, timeout=30):
    headers = {"User-Agent": "find-media/1", "Content-Type": "application/json"}
    key = os.environ.get("TRACE_MOE_KEY")
    if key:
        headers["x-trace-key"] = key
    req = urllib.request.Request(url, data=None if payload is None else
                                 json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4 * 1024 * 1024)
            body = json.loads(raw)
            if not isinstance(body, dict):
                return 0, {"error": "invalid_json_shape"}, {}
            return resp.status, body, {
                k: v for k, v in resp.headers.items()
                if k.lower().startswith(("x-ratelimit", "ratelimit", "retry-after"))}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read(65536))
            if not isinstance(body, dict):
                body = {"error": "non_object_http_error"}
        except (ValueError, UnicodeError, http.client.HTTPException, TimeoutError, urllib.error.URLError):
            body = {"error": "unreadable_http_error_body"}
        return exc.code, body, {"retry-after": exc.headers.get("Retry-After", "")}
    except (urllib.error.URLError, TimeoutError, socket.timeout, http.client.HTTPException):
        return 0, {"error": "network_or_timeout"}, {}
    except (ValueError, UnicodeError):
        return 0, {"error": "invalid_json_response"}, {}

def classify(code, raw):
    if code == 402:
        return "quota_or_concurrency"
    if code == 403:
        return "credentials_error"
    if code in (429, 503, 504):
        return "rate_or_service_limited"
    if code == 0:
        return raw.get("error", "network_or_timeout")
    if code != 200 or raw.get("error"):
        return "provider_error"
    return "ok" if raw.get("result") else "no_match"

def candidates(raw):
    answer = []
    for item in raw.get("result") or []:
        if not isinstance(item, dict):
            continue
        ani = item.get("anilist")
        obj = ani if isinstance(ani, dict) else {}
        ident = obj.get("id") if obj else ani
        title = obj.get("title") or {}
        if isinstance(title, dict):
            name = title.get("native") or title.get("romaji") or title.get("english")
        else:
            name = str(title)
        score = item.get("similarity")
        answer.append({"work_id": {"provider": "anilist", "id": ident},
            "name": name, "aliases": obj.get("synonyms", []),
            "episode": item.get("episode"), "episode_start": item.get("episode_start"),
            "episode_end": item.get("episode_end"), "filename": item.get("filename"),
            "provider_similarity": score,
            "retrieval_hint": "low_similarity" if isinstance(score, (int, float)) and score < .9
                              else "needs_visual_verification",
            "provider_anchor": item.get("at"), "provider_scene": [item.get("from"), item.get("to")],
            "preview": {"image": item.get("image"), "video": item.get("video")},
            "confirmation": {"title": "unverified", "episode": "unverified", "time": "unverified"},
            "raw": item})
    return answer

def search(images, cache_dir, budget=6, retries=1, timeout=30, refresh=False,
           request_fn=request_json, sleep_fn=time.sleep):
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    lock = cache / "trace.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("trace_busy: serialize calls; inspect existing cache lock before removing it") from None
    used, results = 0, []
    try:
        os.write(descriptor, str(os.getpid()).encode())
        me_code, me, me_headers = request_fn(API + "/me", timeout=timeout)
        me = {k: v for k, v in me.items() if k != "id"}
        quota_empty = (me_code == 200 and isinstance(me.get("quota"), (int, float))
                       and isinstance(me.get("quotaUsed"), (int, float))
                       and me["quotaUsed"] >= me["quota"])
        for path in images:
            entry = {"input": fingerprint(path), "checked_at": now(), "candidates": []}
            vector_info = json.loads(run(["node", Path(__file__).with_name("trace-vector.mjs"), path],
                                         timeout=timeout).stdout)
            vector = vector_info["vector"]
            if len(vector) != 33 or not all(isinstance(x, (int, float)) and
                                           math.isfinite(x) for x in vector):
                raise ValueError("invalid local vector")
            cache_key = hashlib.sha256(json.dumps(vector).encode()).hexdigest()
            cached = cache / (cache_key + ".json")
            entry["processing"] = vector_info
            if cached.exists() and not refresh and time.time() - cached.stat().st_mtime < 86400:
                saved = load(cached)
                raw, headers, code = saved["raw"], saved["headers"], saved["http_status"]
                entry.update(cache_hit=True, retrieved_at=saved["retrieved_at"],
                             preview_may_be_expired=True)
            else:
                if quota_empty or used >= budget:
                    entry["process_status"] = "quota_exhausted" if quota_empty else "budget_exhausted"
                    results.append(entry)
                    continue
                for attempt in range(retries + 1):
                    if used >= budget:
                        break
                    used += 1
                    code, raw, headers = request_fn(API + "/search?anilistInfo",
                                                   {"vector": vector}, timeout=timeout)
                    status = classify(code, raw)
                    if code not in (429, 503, 504) or attempt == retries or used >= budget:
                        break
                    retry_after = str(headers.get("retry-after", ""))
                    delay = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else 2 ** attempt
                    sleep_fn(min(10, max(1, delay)))
                entry.update(cache_hit=False, retrieved_at=now(), preview_may_be_expired=False)
                if code == 200 and not raw.get("error"):
                    # Replace only this client's own cache; reports/input files remain immutable.
                    tmp = cached.with_suffix(".tmp")
                    tmp.write_text(json.dumps({"raw": raw, "headers": headers, "http_status": code,
                                               "retrieved_at": entry["retrieved_at"]}), encoding="utf-8")
                    tmp.replace(cached)
                sleep_fn(.5)
            entry.update(process_status=classify(code, raw), http_status=code,
                         response_headers=headers, candidates=candidates(raw), raw=raw)
            results.append(entry)
            if code == 402:
                for remaining in images[len(results):]:
                    results.append({"input": fingerprint(remaining), "process_status": "stopped_after_402",
                                    "candidates": [], "checked_at": now()})
                break
        successful = sum(f["process_status"] in ("ok", "no_match") for f in results)
        status = "ok" if successful == len(results) else "partial" if successful else "failed"
        return {"kind": "trace_search", "process_status": status, "checked_at": now(), "data_flow": "local RGB -> local 33D vector -> trace.moe; no image upload",
                "search_attempts": used, "budget": budget,
                "quota_check": {"http_status": me_code, "status": "ok" if me_code == 200 and not me.get("error") else classify(me_code, me),
                                "raw": me, "headers": me_headers}, "frames": results}
    finally:
        os.close(descriptor)
        lock.unlink()
