#!/usr/bin/env python3
"""Build a single self-contained, offline HTML snapshot of the FDIC dashboard.

  python3 export_html.py            # refresh FDIC data first, then export
  python3 export_html.py --no-fetch # export from the current web/data/data.json

Output: FDIC_Dashboard_<YYYY-MM-DD>.html (or --out). CSS, JS, Chart.js + date adapter and the data
are all inlined; the page makes no network calls. The Excel link points to fdic_metrics.xlsx next to
the HTML file (the Pages workflow copies it into _site/).
"""
import argparse, json, os, re, shutil, subprocess, sys, datetime as dt
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")


def read(rel):
    with open(os.path.join(WEB, rel), encoding="utf-8") as f:
        return f.read()


def script_safe(js):
    return js.replace("</script", "<\\/script").replace("<!--", "<\\!--")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--out", help="output path (default: FDIC_Dashboard_<date>.html in this folder)")
    a = ap.parse_args()
    if not a.no_fetch:
        subprocess.run([sys.executable, os.path.join(ROOT, "fetch_data.py")], check=True)

    data = json.loads(read("data/data.json"))
    gen_ct = dt.datetime.fromisoformat(data["generated_utc"]).astimezone(ZoneInfo("America/Chicago"))
    html = read("index.html")
    html = html.replace('<link rel="stylesheet" href="style.css">', f"<style>\n{read('style.css')}\n</style>")
    for lib in ["vendor/chart.umd.min.js", "vendor/chartjs-adapter-date-fns.bundle.min.js"]:
        tag = f'<script src="{lib}"></script>'
        assert tag in html, tag
        html = html.replace(tag, f"<script>/* {lib} */\n{script_safe(read(lib))}\n</script>")
    data_js = "window.__FDIC_DATA__ = " + script_safe(json.dumps(data, separators=(",", ":"))) + ";"
    app_tag = '<script src="app.js"></script>'
    assert app_tag in html
    html = html.replace(app_tag, f"<script>\n{data_js}\n</script>\n<script>\n{script_safe(read('app.js'))}\n</script>")
    html = html.replace("<title>FDIC Banking Dashboard · Aggregate Call Report Metrics</title>",
                        f"<title>FDIC Banking Dashboard · {data['latest_quarter']} · snapshot {gen_ct:%Y-%m-%d %H:%M} CT</title>")
    # sanity: no remaining external resources (plain <a href> links to fdic.gov / the Excel file are fine)
    leftovers = re.findall(r'<(?:script|img|link)[^>]+(?:src|href)="(?!data:|#)[^"]+"', html)
    assert not leftovers, leftovers

    out = a.out or os.path.join(ROOT, f"FDIC_Dashboard_{gen_ct:%Y-%m-%d}.html")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(out + ".tmp", out)
    xl = os.path.join(WEB, "data", "fdic_metrics.xlsx")
    if os.path.exists(xl):
        shutil.copy2(xl, os.path.join(os.path.dirname(os.path.abspath(out)), "fdic_metrics.xlsx"))
    print(f"Wrote {out} ({os.path.getsize(out)/1e6:.2f} MB), data through {data['latest_quarter']}, snapshot {gen_ct:%Y-%m-%d %I:%M %p} CT")


if __name__ == "__main__":
    main()
