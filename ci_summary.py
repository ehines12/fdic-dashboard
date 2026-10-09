#!/usr/bin/env python3
"""Per-group FDIC fetch summary for CI logs (and the GitHub Actions job summary)."""
import json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, "web", "data", "data.json")))
lines = ["| Group | API filter | Status | First | Latest | Quarters | Institutions (latest) | Error |", "|---|---|---|---|---|---:|---:|---|"]
filters = {g["key"]: g["filter"] for g in D["groups"]}
for s in D["status"]:
    st = "OK" if s["ok"] else ("FAILED (STALE kept)" if s.get("stale") else "FAILED")
    lines.append(f"| {s['label']} | `{filters.get(s['group'], '')}` | {st} | {s.get('first', '')} | {s.get('last', '')} | "
                 f"{s.get('quarters', '')} | {s.get('institutions_latest', '')} | {s.get('error', '')} |")
roa = next(r for r in D["summary"] if r["key"] == "roa")["groups"]["all"]
out = (f"**Data built:** {D['generated_utc']} UTC · latest quarter **{D['latest_quarter']}** · industry ROA {roa['latest']:.2f}%\n\n"
       + "\n".join(lines))
print(out)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write(out + "\n")
