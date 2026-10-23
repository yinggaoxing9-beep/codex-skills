#!/usr/bin/env python3
"""Local utilities for Codex find-media. Run --help; no credential required for local work."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from common import ffmpeg_path, load, save_new

def positive(value):
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be finite and positive")
    return number

def positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    a = sub.add_parser("prepare")
    a.add_argument("input"); a.add_argument("--out", required=True)
    a.add_argument("--start", type=float, default=0)
    a.add_argument("--max-duration", type=positive, default=120)
    a.add_argument("--max-frames", type=positive_int, default=24)
    a.add_argument("--gap", type=positive, default=5)
    a.add_argument("--threshold", type=float, default=.3)
    a.add_argument("--blur-threshold", type=float, default=2)
    a.add_argument("--timeout", type=positive, default=90)
    a.add_argument("--ffmpeg")
    a = sub.add_parser("transform")
    a.add_argument("input"); a.add_argument("--out", required=True)
    a.add_argument("--mirror", action="store_true")
    a.add_argument("--black-border", action="store_true")
    a.add_argument("--crop", type=int, nargs=4, metavar=("LEFT","TOP","RIGHT","BOTTOM"))
    a = sub.add_parser("trace")
    a.add_argument("images", nargs="+"); a.add_argument("--out", required=True)
    a.add_argument("--cache", required=True)
    a.add_argument("--budget", type=positive_int, default=6)
    a.add_argument("--retries", type=int, choices=range(3), default=1)
    a.add_argument("--timeout", type=positive, default=30)
    a.add_argument("--refresh", action="store_true")
    a = sub.add_parser("subtitle")
    a.add_argument("input"); a.add_argument("--query", required=True)
    a.add_argument("--version"); a.add_argument("--encoding", default="utf-8-sig")
    a.add_argument("--out", required=True)
    a = sub.add_parser("compare")
    a.add_argument("query"); a.add_argument("--source", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--start", type=float, required=True); a.add_argument("--end", type=float, required=True)
    a.add_argument("--step", type=positive, default=1)
    a.add_argument("--max-frames", type=positive_int, default=120)
    a.add_argument("--timeout", type=positive, default=60); a.add_argument("--ffmpeg")
    a = sub.add_parser("report")
    a.add_argument("input"); a.add_argument("--out")
    args = vars(p.parse_args())
    command = args.pop("command")
    if command == "doctor":
        try:
            ffmpeg = ffmpeg_path()
        except ValueError:
            ffmpeg = None
        root = Path(__file__).resolve().parent.parent
        answer = {"python": sys.version.split()[0], "pillow": bool(importlib.util.find_spec("PIL")),
                  "ffmpeg": ffmpeg, "ffprobe": shutil.which("ffprobe"), "node": shutil.which("node"),
                  "local_node_dependencies": all((root/"node_modules"/m).exists() for m in ("sharp","trace.moe-id")),
                  "search_tools": "Codex must discover connected search/browser tools; CLI does not assume them",
                  "credentials": "optional TRACE_MOE_KEY; never print its value"}
    elif command == "prepare":
        from media import prepare
        args["source"] = args.pop("input")
        answer = prepare(**args)
    elif command == "transform":
        from media import transform
        args["source"], args["target"] = args.pop("input"), args.pop("out")
        answer = transform(**args)
    elif command == "trace":
        from trace_search import search
        output = args.pop("out")
        if Path(output).exists():
            raise ValueError("output_exists")
        args["cache_dir"] = args.pop("cache")
        answer = search(**args)
        save_new(output, answer)
    elif command == "subtitle":
        from subtitles import search
        path, output = args.pop("input"), args.pop("out")
        if Path(output).exists():
            raise ValueError("output_exists")
        answer = search(path, **args)
        save_new(output, answer)
    elif command == "compare":
        from media import compare
        answer = compare(**args)
    else:
        from contract import render
        text = render(load(args["input"]))
        if args["out"]:
            with Path(args["out"]).open("x", encoding="utf-8") as stream:
                stream.write(text)
        print(text)
        return
    if command == "trace":
        print(json.dumps({"output": output, "process_status": answer["process_status"], "search_attempts": answer["search_attempts"],
                          "frames": [{"input": f["input"], "status": f["process_status"],
                                      "candidate_count": len(f["candidates"])} for f in answer["frames"]]},
                         ensure_ascii=False, indent=2))
        if answer["process_status"] == "failed":
            raise SystemExit(2)
    else:
        print(json.dumps(answer, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, OSError, ImportError, KeyError, TypeError) as exc:
        print(json.dumps({"process_status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
