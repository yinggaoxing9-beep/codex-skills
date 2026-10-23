"""Shared local helpers. No network or installation side effects on import."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat()

def fingerprint(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return {"path": str(Path(path).resolve()), "sha256": h.hexdigest()}

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def save_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)

def run(args, timeout=60):
    try:
        p = subprocess.run([str(x) for x in args], capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise ValueError("dependency_missing: " + str(args[0])) from None
    except subprocess.TimeoutExpired:
        raise ValueError("process_timeout: " + str(args[0])) from None
    if p.returncode:
        raise ValueError("process_failed: " + p.stderr.decode("utf-8", errors="replace")[-1800:])
    return p

def ffmpeg_path(explicit=None):
    value = explicit or os.environ.get("FIND_MEDIA_FFMPEG") or shutil.which("ffmpeg")
    if value:
        return value
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise ValueError("dependency_missing: ffmpeg; provide --ffmpeg or FIND_MEDIA_FFMPEG") from None
