"""Validate inclusive report dates without consulting the host clock."""
import argparse
import json
from datetime import date, datetime, time, timedelta, timezone

ZONES = {"UTC": timezone.utc, "Asia/Shanghai": timezone(timedelta(hours=8))}

def window(start, end, zone="UTC", allow_nonweekly=False):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    days = (b-a).days+1
    if days <= 0:
        raise ValueError("end date must not precede start date")
    if days != 7 and not allow_nonweekly:
        raise ValueError(f"{start}—{end} includes {days} complete dates, not 7; confirm the requested range (never silently drop a date)")
    tz = ZONES[zone]
    left = datetime.combine(a, time(), tz)
    right = datetime.combine(b+timedelta(days=1), time(), tz)
    previous = left-timedelta(days=days)
    def bounds(x, y):
        return {"start_inclusive":x.isoformat(), "end_exclusive":y.isoformat(),
                "utc_start":x.astimezone(timezone.utc).isoformat(), "utc_end":y.astimezone(timezone.utc).isoformat(),
                "bjt_start":x.astimezone(ZONES["Asia/Shanghai"]).isoformat(), "bjt_end":y.astimezone(ZONES["Asia/Shanghai"]).isoformat()}
    return {"start_date":start, "end_date":end, "timezone":zone, "days":days,
            **bounds(left,right), "comparison":{"start_date":previous.date().isoformat(),
            "end_date":(left-timedelta(days=1)).date().isoformat(), **bounds(previous,left)}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start");p.add_argument("--end")
    p.add_argument("--as-of",help="Explicit aware client timestamp; derives latest 7 completed days in selected timezone")
    p.add_argument("--timezone",choices=list(ZONES),default="UTC")
    p.add_argument("--allow-nonweekly",action="store_true")
    args=p.parse_args()
    try:
        if args.as_of:
            if args.start or args.end: raise ValueError("use --as-of OR --start and --end")
            current=datetime.fromisoformat(args.as_of.replace("Z","+00:00"))
            if current.utcoffset() is None: raise ValueError("--as-of must include timezone offset")
            last=current.astimezone(ZONES[args.timezone]).date()-timedelta(days=1)
            first=last-timedelta(days=6)
            result=window(first.isoformat(),last.isoformat(),args.timezone)
            result["as_of"]=current.isoformat()
        else:
            if not args.start or not args.end: raise ValueError("provide --start and --end, or explicit --as-of")
            result=window(args.start,args.end,args.timezone,args.allow_nonweekly)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,TypeError) as exc:
        p.error(str(exc))

if __name__=="__main__": main()
