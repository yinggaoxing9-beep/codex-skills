"""FFmpeg scene sampling and bounded local frame comparison; no library index."""
import math
from pathlib import Path
import re
import shutil
import subprocess
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat
from common import ffmpeg_path, fingerprint, now, run, save_new

def duration(path, ffmpeg):
    # ffprobe is optional; ffmpeg's demuxer duration is sufficient for bounded sampling.
    p = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                       capture_output=True, timeout=30)
    message = p.stderr.decode("utf-8", errors="replace")
    found = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", message)
    if not found:
        raise ValueError("duration_unknown: specify readable local media with a finite duration")
    h, m, s = map(float, found.groups())
    return h * 3600 + m * 60 + s

def scene_ranges(start, end, cuts):
    points = [start] + sorted(set(c for c in cuts if start + .001 < c < end - .001)) + [end]
    return [(a, b) for a, b in zip(points, points[1:]) if b > a]

def frame_plan(ranges, gap=5):
    # First one frame per scene, then another, then periodic coverage.
    first, second, extra = [], [], []
    for i, (a, b) in enumerate(ranges):
        first.append((i, (a+b)/2))
        second.append((i, a + min(.15, (b-a)/4)))
        t = a + gap
        while t < b:
            extra.append((i, t))
            t += gap
    seen, out = set(), []
    for i, t in first + second + extra:
        key = (i, round(t, 4))
        if key not in seen:
            seen.add(key)
            out.append((i, t))
    return out

def extract(ffmpeg, source, t, output, timeout):
    run([ffmpeg, "-v", "error", "-nostdin", "-ss", f"{t:.6f}", "-i", source,
         "-frames:v", "1", "-vf", "scale=960:960:force_original_aspect_ratio=decrease",
         "-n", output], timeout=timeout)
    if not Path(output).exists():
        raise ValueError("frame_not_decoded")

def image_quality(path):
    with Image.open(path) as im:
        gray = im.convert("L").resize((128, 128))
        histogram = gray.histogram()
        black = sum(histogram[:10]) / sum(histogram) > .99
        edge_var = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0]
        return {"black": black, "edge_variance": round(edge_var, 4)}

def prepare(source, out, start=0, max_duration=120, max_frames=24, gap=5,
            threshold=.3, blur_threshold=2, timeout=90, ffmpeg=None):
    ffmpeg = ffmpeg_path(ffmpeg)
    if not 0 <= threshold <= 1 or not math.isfinite(start):
        raise ValueError("invalid start or scene threshold")
    source = str(Path(source).resolve())
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("output_exists: use a new work directory")
    total = duration(source, ffmpeg)
    end = min(total, start + max_duration)
    if start < 0 or start >= end:
        raise ValueError("invalid input range")
    out.mkdir(parents=True)
    # Input seek resets decoded timestamps; showinfo timestamps are relative to start.
    cuts = []
    detector = {"method": "ffmpeg_scene_score", "threshold": threshold, "status": "ok"}
    try:
        p = run([ffmpeg, "-hide_banner", "-nostdin", "-ss", start, "-i", source,
                 "-t", end-start, "-vf", f"select='gt(scene,{threshold})',showinfo",
                 "-an", "-f", "null", "-"], timeout)
        pts = re.findall(r"pts_time:([\d.]+)", p.stderr.decode("utf-8", errors="replace"))
        cuts = [start + float(t) for t in pts]
    except ValueError as exc:
        detector.update(status="failed_uniform_fallback", detail=str(exc))
    ranges = scene_ranges(start, end, cuts)
    plan = frame_plan(ranges, gap)
    records, seen = [], {}
    for number, (scene, t) in enumerate(plan[:max_frames]):
        target = out / f"frame-{number:04d}-{t:.4f}.png"
        row = {"id": f"f{number:04d}", "scene_id": scene,
               "input_time": t, "path": str(target), "processing": ["decode", "scale_inside_960"],
               "status": "selected", "lookup_status": "not_queried"}
        try:
            extract(ffmpeg, source, t, target, timeout)
            row.update(image_quality(target))
            row["sha256"] = fingerprint(target)["sha256"]
            if row["black"]:
                row["status"] = "filtered_black"
            elif row["edge_variance"] < blur_threshold:
                row["status"] = "filtered_low_detail_or_blur"
            elif (scene, row["sha256"]) in seen:
                row.update(status="duplicate", duplicate_of=seen[(scene, row["sha256"])])
            else:
                seen[(scene, row["sha256"])] = row["id"]
        except ValueError as exc:
            row.update(status="decode_failed", detail=str(exc))
        records.append(row)
    scenes = []
    for i, (a, b) in enumerate(ranges):
        usable = [r["id"] for r in records if r["scene_id"] == i and r["status"] == "selected"]
        scenes.append({"id": i, "input_range": [a, b], "selected_frames": usable,
                       "status": "sampled_not_identified" if usable else "unprocessed"})
    manifest = {"kind": "media_prepare", "input": fingerprint(source), "checked_at": now(),
                "total_duration": total, "analyzed_input_range": [start, end],
                "unprocessed_input_ranges": ([[0, start]] if start else []) +
                                             ([[end, total]] if end < total else []),
                "scene_detector": detector, "scene_count": len(ranges), "scenes": scenes,
                "frames": records, "selected_count": sum(r["status"] == "selected" for r in records),
                "attempted_frame_count": len(records), "planned_frame_count": len(plan),
                "stop_reason": "frame_budget" if len(plan) > max_frames else
                               "duration_budget" if end < total else "sample_plan_complete",
                "lookup_coverage": {"queried_frame_ids": [], "note": "sampling is not source identification"},
                "precision": {"clock": "input decoded timeline seconds", "seek_error": "codec dependent; inspect anchors"},
                "ffmpeg_version": run([ffmpeg, "-version"]).stdout.decode(errors="replace").splitlines()[0]}
    save_new(out / "manifest.json", manifest)
    return manifest

def transform(source, target, mirror=False, crop=None, black_border=False):
    if Path(target).exists() or Path(str(target) + ".provenance.json").exists():
        raise ValueError("output_exists")
    operations = []
    with Image.open(source) as original:
        im = ImageOps.exif_transpose(original).convert("RGB")
        operations.append("exif_orientation")
        if black_border:
            # Conservative constant dark border trim, not an automatic semantic video crop.
            box = im.point(lambda p: 255 if p > 12 else 0).getbbox()
            if box:
                im = im.crop(box)
                operations.append({"black_border_bbox": list(box)})
        if crop:
            if not (0 <= crop[0] < crop[2] <= im.width and 0 <= crop[1] < crop[3] <= im.height):
                raise ValueError("crop_outside_image")
            im = im.crop(crop)
            operations.append({"crop_bbox": crop})
        if mirror:
            im = ImageOps.mirror(im)
            operations.append("horizontal_mirror")
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with Path(target).open("xb") as stream:
            im.save(stream, format="PNG")
    result = {"kind": "image_derivative", "input": fingerprint(source), "output": fingerprint(target),
              "processing": operations, "checked_at": now()}
    save_new(str(target) + ".provenance.json", result)
    return result

def distance(first, second):
    # Pillow local pixel distance is a retrieval score, not a verification/confidence probability.
    with Image.open(first) as a, Image.open(second) as b:
        a = ImageOps.exif_transpose(a).convert("RGB").resize((64, 64))
        b = ImageOps.exif_transpose(b).convert("RGB").resize((64, 64))
        return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3

def compare(query, source, out, start, end, step=1, max_frames=120, timeout=60, ffmpeg=None):
    ffmpeg = ffmpeg_path(ffmpeg)
    total = duration(source, ffmpeg)
    if not (0 <= start < end <= total + .001) or step <= 0:
        raise ValueError("invalid comparison range or sampling step")
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("output_exists")
    out.mkdir(parents=True)
    count = min(max_frames, math.ceil((end-start)/step))
    rows = []
    for i in range(count):
        t = start + i * step
        target = out / f"source-{i:04d}-{t:.4f}.png"
        extract(ffmpeg, source, t, target, timeout)
        rows.append({"source_time": t, "path": str(target), "pixel_mae": distance(query, target)})
    rows.sort(key=lambda r: r["pixel_mae"])
    result = {"kind": "local_frame_comparison", "query": fingerprint(query), "source": fingerprint(source),
              "requested_range": [start, end], "sample_times": [start+i*step for i in range(count)],
              "sampling_step": step, "checked_at": now(), "candidates": rows[:8],
              "stop_reason": "frame_budget" if count < math.ceil((end-start)/step) else "range_sampled",
              "confirmation": "unverified", "time_basis": "provided_source_file_decoded_seconds",
              "precision": "sampling step; visual verification required; no interval extrapolation"}
    save_new(out / "comparison.json", result)
    return result
