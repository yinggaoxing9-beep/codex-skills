"""Validate evidence/status separation and render a concise Chinese result."""
import math
from common import load

def seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

def time_range(value):
    return isinstance(value, list) and len(value) == 2 and all(seconds(v) for v in value) and value[0] < value[1]

LEVELS = {"unverified", "confirmed", "rejected"}
KINDS = {"anime", "live_action", "game", "plot"}
STATUSES = {"unresolved", "title_only", "episode_only", "verified_anchor", "verified_interval"}

def validate(report):
    errors = []
    if report.get("schema_version") != 1 or report.get("task_type") not in KINDS:
        errors.append("schema_version/task_type invalid")
    for key in ("inputs", "segments", "process", "coverage", "unresolved", "next_steps"):
        if key not in report:
            errors.append("missing " + key)
    for i, seg in enumerate(report.get("segments", [])):
        prefix = f"segments[{i}]"
        status = seg.get("status")
        if seg.get("input_range") is not None and not time_range(seg["input_range"]):
            errors.append(prefix + ": invalid input range")
        if status not in STATUSES:
            errors.append(prefix + ": invalid status")
        confirm = seg.get("confirmation", {})
        if any(confirm.get(k) not in LEVELS for k in ("title", "episode", "time")):
            errors.append(prefix + ": independent confirmation levels required")
        evidence = seg.get("evidence", [])
        ids = {e.get("id") for e in evidence}
        if len(ids) != len(evidence) or None in ids:
            errors.append(prefix + ": evidence ids required/unique")
        for e in evidence:
            if not e.get("source") or not e.get("checked_at") or not e.get("observation"):
                errors.append(prefix + ": evidence needs source, date and actual observation")
        confirmed = [k for k, v in confirm.items() if v == "confirmed"]
        support = seg.get("confirmation_evidence", {})
        for level in confirmed:
            refs = support.get(level, [])
            if not refs or not all(ref in ids for ref in refs):
                errors.append(prefix + ": confirmed " + level + " requires evidence references")
        required = {"title_only": ["title"], "episode_only": ["title", "episode"],
                    "verified_anchor": ["title", "time"], "verified_interval": ["title", "time"]}.get(status, [])
        if any(confirm.get(k) != "confirmed" for k in required):
            errors.append(prefix + ": status exceeds evidence levels")
        if status == "episode_only" and confirm.get("time") == "confirmed":
            errors.append(prefix + ": episode_only contradicts confirmed time")
        if status != "verified_interval" and seg.get("source_interval") is not None:
            errors.append(prefix + ": source interval requires verified_interval")
        if status == "title_only" and (confirm.get("episode") == "confirmed" or confirm.get("time") == "confirmed"):
            errors.append(prefix + ": title_only contradicts confirmed episode/time")
        if confirm.get("time") == "confirmed":
            basis = seg.get("time_basis", {})
            if not basis.get("version") or not basis.get("clock") or not basis.get("precision"):
                errors.append(prefix + ": confirmed time requires version/clock/precision")
            if "error" not in basis:
                errors.append(prefix + ": state timing error or unknown explicitly")
        if status in ("verified_anchor", "verified_interval"):
            anchors = seg.get("anchors", [])
            if not anchors or any(not seconds(a.get("source_time")) or
                                  not seconds(a.get("input_time")) or
                                  a.get("evidence_id") not in ids or a.get("reviewed") is not True
                                  for a in anchors):
                errors.append(prefix + ": reviewed anchor evidence required")
        if status in ("verified_anchor", "verified_interval") and time_range(seg.get("input_range")) and any(
                not seconds(a.get("input_time")) or not seg["input_range"][0] <= a["input_time"] <= seg["input_range"][1]
                for a in seg.get("anchors", [])):
            errors.append(prefix + ": input anchors outside input interval")
        if status == "verified_interval":
            interval = seg.get("source_interval")
            if len(seg.get("anchors", [])) < 2 or not time_range(interval):
                errors.append(prefix + ": ordered interval and multiple anchors required")
            elif any(not seconds(a.get("source_time")) or not interval[0] <= a["source_time"] <= interval[1]
                     for a in seg.get("anchors", [])):
                errors.append(prefix + ": source anchors outside verified source interval")
            continuity = seg.get("continuity", {})
            if continuity.get("reviewed_source_span") is not True or continuity.get("evidence_id") not in ids:
                errors.append(prefix + ": source-span verification required; anchors alone do not prove continuity")
        if seg.get("excluded") and not seg.get("exclusion_reason"):
            errors.append(prefix + ": exclusion reason required")
    return errors

def render(report):
    errors = validate(report)
    if errors:
        raise ValueError("invalid report: " + "; ".join(errors))
    def cell(value):
        return str(value).replace("|", "／").replace("\n", " ")
    def link(value):
        value = str(value)
        return f"[来源]({value})" if value.startswith(("http://", "https://")) else value
    labels = {"unresolved": "未解决", "title_only": "作品确认", "episode_only": "作品/集数确认",
              "verified_anchor": "锚点核验", "verified_interval": "连续区间核验"}
    levels = {"confirmed": "已确认", "unverified": "未确认", "rejected": "已否定"}
    lines = ["| 输入段 | 作品/候选 | 季/集 | 状态 | 原片定位(秒) |",
             "| --- | --- | --- | --- | --- |"]
    for seg in report["segments"]:
        work = seg.get("work", {})
        timing = seg.get("source_interval") or [a["source_time"] for a in seg.get("anchors", [])]
        episode = seg.get("episode")
        if isinstance(episode, dict):
            episode = str(episode) + "（候选）"
        row = [seg.get("input_range") or "描述/图片", work.get("name") or "未解决",
               f"{seg.get('season', '未知')}/{episode if episode is not None else '未知'}",
               labels[seg["status"]], timing or "未确认"]
        lines.append("| " + " | ".join(cell(v) for v in row) + " |")
    for seg in report["segments"]:
        lines.append("\n" + str(seg.get("id", "片段")) + "：" + "；".join(
            label + levels[seg["confirmation"][key]]
            for key, label in (("title", "作品"), ("episode", "集数"), ("time", "时间"))))
        for field, label in (("clue_matches", "符合"), ("clue_conflicts", "冲突"), ("clue_unknowns", "未知")):
            if seg.get(field):
                lines.append(f"\n{label}：{'；'.join(seg[field])}")
        for e in seg.get("evidence", []):
            lines.append(f"\n证据 {e['id']}：{e['observation']}（{link(e['source'])}，{e['checked_at']}）")
        if seg.get("time_basis"):
            basis=seg["time_basis"]
            lines.append(f"\n时间基准：{basis.get('version')}；{basis.get('clock')}；"
                         f"精度：{basis.get('precision')}；误差：{basis.get('error') if basis.get('error') is not None else '未知'}")
        for entry in seg.get("watch_entries", []):
            lines.append(f"\n入口：{link(entry.get('url'))}；地区 {entry.get('region', 'unknown')}；"
                         f"{entry.get('kind')}；核验 {entry.get('checked_at')}；{entry.get('availability', 'unknown')}")
        if seg.get("excluded"):
            lines.append("\n已排除：" + seg["exclusion_reason"])
    lines.append("\n覆盖：" + str(report["coverage"]))
    lines.append("\n过程：" + str(report["process"]))
    lines.append("\n未解决：" + "；".join(report["unresolved"]))
    lines.append("\n下一步：" + "；".join(report["next_steps"]))
    return "\n".join(lines)
