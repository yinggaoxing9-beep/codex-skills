"""SRT/VTT/ASS dialogue anchors, retaining all repeated matches."""
import re
import unicodedata
from common import fingerprint, now

def stamp(text):
    parts = text.strip().replace(",", ".").split(":")
    if len(parts) not in (2, 3):
        raise ValueError("invalid subtitle timestamp")
    return sum(float(p) * (60 ** i) for i, p in enumerate(reversed(parts)))

def clean(text):
    text = re.sub(r"\{[^}]*\}|<[^>]*>", "", text)
    return text.replace(r"\N", " ").replace(r"\n", " ").strip()

def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", clean(text)).casefold()
                   if c.isalnum())

def parse(text, suffix):
    if suffix.lower() in (".ass", ".ssa"):
        fields = None
        in_events = False
        for line in text.splitlines():
            if line.strip().startswith("["):
                in_events = line.strip().lower() == "[events]"
            if not in_events:
                continue
            if line.lower().startswith("format:"):
                fields = [f.strip().lower() for f in line.split(":", 1)[1].split(",")]
            if line.lower().startswith("dialogue:"):
                if not fields or not all(f in fields for f in ("start", "end", "text")):
                    raise ValueError("ASS Events Format missing required fields")
                values = line.split(":", 1)[1].lstrip().split(",", len(fields) - 1)
                row = dict(zip(fields, values))
                yield {"start": stamp(row["start"]), "end": stamp(row["end"]),
                       "text": clean(row["text"])}
    else:
        lines = text.replace("\r\n", "\n").splitlines()
        for i, line in enumerate(lines):
            if "-->" not in line:
                continue
            left, right = line.split("-->", 1)
            try:
                start, end = stamp(left), stamp(right.strip().split()[0])
            except ValueError:
                continue
            body = []
            for following in lines[i+1:]:
                if not following.strip():
                    break
                body.append(following)
            yield {"start": start, "end": end, "text": clean(" ".join(body))}

def search(path, query, version=None, encoding="utf-8-sig"):
    from pathlib import Path
    needle = normalized(query)
    if not needle:
        raise ValueError("empty dialogue query")
    rows = list(parse(Path(path).read_text(encoding=encoding), Path(path).suffix))
    matches = [r for r in rows if needle in normalized(r["text"])]
    return {"kind": "subtitle_search", "input": fingerprint(path), "query": query,
            "checked_at": now(), "matches": matches, "cue_count": len(rows),
            "process_status": "ok" if matches else "no_match",
            "time_basis": {"kind": "subtitle_clock", "version": version,
                           "offset_to_video": None, "precision_seconds": 0.001},
            "localization": "unverified", "warnings": [
                "Dialogue can repeat; subtitle clock is not a verified video clock.",
                "Version/offset unknown unless independently compared with the source video."]}
