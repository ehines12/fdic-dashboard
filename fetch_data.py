#!/usr/bin/env python3
"""Fetch FDIC aggregate banking data and write web/data/data.json (+ fdic_metrics.xlsx).

Source: FDIC BankFind Suite API, /banks/financials (Call Report data for every FDIC-insured
institution), summed by report date with the API's aggregation (agg_by=REPDTE).
Groups: all insured institutions, community banks (FDIC definition, CB=1), and banks with
$10B-$250B total assets. Insured U.S. branches of foreign banks are excluded (IBA=0), as in the QBP.

Fallback: if a group fails to download, the previous copy of that group's series in
web/data/data.json is kept and flagged STALE (same idea as the Financials Dashboard).
"""
import json, os, sys, time, datetime as dt
import requests
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "web", "data")
OUT_JSON = os.path.join(DATA_DIR, "data.json")
OUT_XLSX = os.path.join(DATA_DIR, "fdic_metrics.xlsx")
API = "https://api.fdic.gov/banks/financials"
FETCH_START = "19981231"      # extra history so YoY growth and averages exist from the chart start
CHART_START = "2000-01-01"

STOCK = ["ASSET", "DEP", "DEPI", "LNLSGR", "LNATRES", "EQ", "ERNAST", "NCLNLS", "RBCT1J", "AVASSETJ"]
FLOW = ["NETINCQ", "ELNATQ", "NTLNLSQ", "EDEPDOMQ", "EDEPFORQ", "NIMQ", "NONIIQ", "NONIXQ"]

GROUPS = [  # (key, label, API filter)
    ("all", "All insured institutions", "IBA:0"),
    ("cb", "Community banks (FDIC def.)", "IBA:0 AND CB:1"),
    ("mid", "Banks $10B–$250B", "IBA:0 AND ASSET:[10000000 TO 249999999]"),
]

# key, title, section, groups shown, polarity (+1 higher is better, -1 lower is better, 0 neutral), note
METRICS = [
    ("roe", "Return on equity (annualized, %)", "Profitability", True, 1, "Net income ×4 / avg total equity"),
    ("roa", "Return on assets (annualized, %)", "Profitability", True, 1, "Net income ×4 / avg total assets"),
    ("nim", "Net interest margin (%)", "Profitability", True, 1, "Net interest income ×4 / avg earning assets"),
    ("eff", "Efficiency ratio (%)", "Profitability", True, -1, "Noninterest expense / (net interest income + noninterest income)"),
    ("prov", "Provision expense / avg loans (annualized, %)", "Credit Quality", True, -1, "Provision for credit losses ×4 / avg total loans"),
    ("nco", "Net charge-off rate (annualized, %)", "Credit Quality", True, -1, "Net charge-offs ×4 / avg total loans"),
    ("ncl", "Noncurrent loans / total loans (%)", "Credit Quality", True, -1, "90+ days past due + nonaccrual / total loans (quarter-end)"),
    ("res", "Loan loss reserves / total loans (%)", "Credit Quality", True, 0, "Allowance for loan & lease losses / total loans (quarter-end)"),
    ("dcost", "Cost of total deposits (annualized, %)", "Funding & Deposits", True, -1, "Deposit interest expense ×4 / avg total deposits (incl. noninterest-bearing)"),
    ("ibcost", "Cost of interest-bearing deposits (annualized, %)", "Funding & Deposits", True, -1, "Deposit interest expense ×4 / avg interest-bearing deposits"),
    ("depg", "Deposit growth YoY (%)", "Funding & Deposits", False, 0, "Industry only (size-group growth is distorted by banks migrating between groups)"),
    ("ldr", "Loan-to-deposit ratio (%)", "Funding & Deposits", True, 0, "Total loans / total deposits (quarter-end)"),
    ("assetg", "Total asset growth YoY (%)", "Growth", False, 0, "Industry only. Total assets vs 4 quarters earlier"),
    ("assetq", "Total asset growth QoQ annualized (%)", "Growth", False, 0, "Industry only. (Assets / prior-quarter assets)^4 − 1"),
    ("loang", "Loan growth YoY (%)", "Growth", False, 0, "Industry only. Total loans & leases vs 4 quarters earlier"),
    ("lev", "Tier 1 leverage ratio (%)", "Capital", True, 1, "Tier 1 capital / average assets for leverage purposes (summed)"),
    ("cet1", "CET1 ratio, RWA reporters (%)", "Capital", False, 1, "CET1 capital / risk-weighted assets, institutions reporting RWA only (excl. CBLR electors from 2020); from 2015"),
    ("eqa", "Equity / total assets (%)", "Capital", True, 1, "Total equity capital / total assets (quarter-end)"),
]

RECESSIONS = [["2001-03-01", "2001-11-30", "2001"], ["2007-12-01", "2009-06-30", "GFC"], ["2020-02-01", "2020-04-30", "COVID"]]


def fetch(extra_filter, fields):
    end = dt.date.today().strftime("%Y%m%d")
    params = dict(filters=f"REPDTE:[{FETCH_START} TO {end}] AND {extra_filter}", agg_by="REPDTE",
                  agg_sum_fields=",".join(fields), agg_limit=500, limit=1, format="json")
    last = None
    for attempt in range(4):
        try:
            r = requests.get(API, params=params, timeout=180)
            r.raise_for_status()
            rows = [x["data"] for x in r.json()["data"]]
            if not rows:
                raise ValueError("empty response")
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["REPDTE"], format="%Y%m%d")
            df = df.set_index("date").sort_index()
            df = df.rename(columns={f"sum_{c}": c for c in fields}).rename(columns={"count": "N_INST"})
            return df.drop(columns=["REPDTE"])
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"FDIC API failed: {last}")


def metrics(d):
    avg = lambda c: (d[c] + d[c].shift(1)) / 2   # 2-point average of prior & current quarter-end
    edep = d["EDEPDOMQ"] + d["EDEPFORQ"]
    m = pd.DataFrame(index=d.index)
    m["roe"] = d["NETINCQ"] * 4 / avg("EQ") * 100
    m["roa"] = d["NETINCQ"] * 4 / avg("ASSET") * 100
    m["nim"] = d["NIMQ"] * 4 / avg("ERNAST") * 100
    m["eff"] = d["NONIXQ"] / (d["NIMQ"] + d["NONIIQ"]) * 100
    m["prov"] = d["ELNATQ"] * 4 / avg("LNLSGR") * 100
    m["nco"] = d["NTLNLSQ"] * 4 / avg("LNLSGR") * 100
    m["ncl"] = d["NCLNLS"] / d["LNLSGR"] * 100
    m["res"] = d["LNATRES"] / d["LNLSGR"] * 100
    m["dcost"] = edep * 4 / avg("DEP") * 100
    m["ibcost"] = edep * 4 / avg("DEPI") * 100
    m["depg"] = d["DEP"].pct_change(4, fill_method=None) * 100
    m["ldr"] = d["LNLSGR"] / d["DEP"] * 100
    m["assetg"] = d["ASSET"].pct_change(4, fill_method=None) * 100
    m["assetq"] = ((d["ASSET"] / d["ASSET"].shift(1)) ** 4 - 1) * 100
    m["loang"] = d["LNLSGR"].pct_change(4, fill_method=None) * 100
    m["lev"] = d["RBCT1J"] / d["AVASSETJ"] * 100
    m["eqa"] = d["EQ"] / d["ASSET"] * 100
    return m


def qlabel(ts):
    ts = pd.Timestamp(ts)
    return f"Q{(ts.month - 1) // 3 + 1} {ts.year}"


def to_pairs(s):
    s = s[s.index >= CHART_START].dropna()
    return [[t.strftime("%Y-%m-%d"), round(float(v), 4)] for t, v in s.items()]


def main():
    prev = None
    if os.path.exists(OUT_JSON):
        try:
            prev = json.load(open(OUT_JSON))
        except Exception:  # noqa: BLE001
            prev = None
    now = dt.datetime.now(dt.timezone.utc)
    series, status, raw = {}, [], {}
    for key, label, flt in GROUPS:
        print(f"Fetching {label} ...", flush=True)
        try:
            df = fetch(flt, STOCK + FLOW)
            raw[key] = df
            m = metrics(df)
            if key == "all":
                cet = fetch("IBA:0 AND RWAJ:[1 TO *] AND REPDTE:[20150331 TO 99999999]", ["RBCT1C", "RWAJ"])
                raw["cet1"] = cet
                m["cet1"] = (cet["RBCT1C"] / cet["RWAJ"] * 100).where(cet["RBCT1C"] > 0)
            series[key] = {k: to_pairs(m[k]) for k in m.columns}
            last = df.index[-1]
            status.append({"group": key, "label": label, "ok": True, "stale": False, "first": qlabel(df.index[0]),
                           "last": qlabel(last), "quarters": len(df), "institutions_latest": int(df["N_INST"].iloc[-1])})
            print(f"  OK {label}: {len(df)} quarters, latest {qlabel(last)}, {int(df['N_INST'].iloc[-1])} institutions")
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED {label}: {e}", flush=True)
            if prev and key in prev.get("series", {}):
                series[key] = prev["series"][key]
                old = next((s for s in prev.get("status", []) if s["group"] == key), {})
                status.append({**old, "group": key, "label": label, "ok": False, "stale": True, "error": str(e)[:300]})
            else:
                status.append({"group": key, "label": label, "ok": False, "stale": False, "error": str(e)[:300]})

    if not any(s["ok"] for s in status) and prev:
        print("All FDIC requests failed; keeping previous data.json (flagged STALE).")
        prev["status"] = status
        prev["last_attempt_utc"] = now.isoformat(timespec="seconds")
        json.dump(prev, open(OUT_JSON, "w"), separators=(",", ":"))
        return 0
    if "all" not in series:
        print("No industry data and no cache; aborting.")
        return 1

    latest = series["all"]["roa"][-1][0]
    # summary: latest / quarter-ago / year-ago for every metric & group
    summary = []
    for key, title, sec, by_group, pol, note in METRICS:
        row = {"key": key, "title": title, "section": sec, "polarity": pol, "groups": {}}
        for g, _, _ in GROUPS:
            if (g != "all" and not by_group) or g not in series or key not in series[g]:
                continue
            pts = dict((d, v) for d, v in series[g][key])
            dates = sorted(pts)
            if not dates:
                continue
            ld = dates[-1]
            idx = dates.index(ld)
            q = pts[dates[idx - 1]] if idx >= 1 else None
            y = pts[dates[idx - 4]] if idx >= 4 else None
            row["groups"][g] = {"asof": ld, "latest": pts[ld], "q_ago": q, "y_ago": y}
        summary.append(row)

    data = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "latest_date": latest, "latest_quarter": qlabel(latest),
        "groups": [{"key": k, "label": l, "filter": f} for k, l, f in GROUPS],
        "metrics": [{"key": k, "title": t, "section": s, "by_group": b, "polarity": p, "note": n} for k, t, s, b, p, n in METRICS],
        "series": series, "summary": summary, "status": status, "recessions": RECESSIONS,
        "source": {"api": API, "fields": "https://api.fdic.gov/banks/docs/risview_properties.yaml",
                   "qbp": "https://www.fdic.gov/quarterly-banking-profile"},
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = OUT_JSON + ".tmp"
    json.dump(data, open(tmp, "w"), separators=(",", ":"))
    os.replace(tmp, OUT_JSON)
    print(f"Wrote {OUT_JSON}: latest {qlabel(latest)}")

    # Excel download (only when all groups are fresh, so the workbook always matches the API)
    if len(raw) >= len(GROUPS) + 1:
        try:
            write_excel(data, raw)
        except Exception as e:  # noqa: BLE001
            print("Excel export failed:", e)
    return 0


def write_excel(data, raw):
    titles = {m["key"]: m["title"] for m in data["metrics"]}
    def frame(g):
        cols = {}
        for k, pts in data["series"][g].items():
            cols[titles.get(k, k)] = pd.Series({pd.Timestamp(d): v for d, v in pts})
        df = pd.DataFrame(cols).sort_index()
        df = df[[titles[m["key"]] for m in data["metrics"] if titles[m["key"]] in df.columns]]
        df.insert(0, "Quarter", [qlabel(t) for t in df.index]); df.index = df.index.date; df.index.name = "Report date"
        return df
    def rawf(df):
        df = df[df.index >= "1999-01-01"].copy()
        df.insert(0, "Quarter", [qlabel(t) for t in df.index]); df.index = df.index.date; df.index.name = "Report date"
        return df
    notes = [("Source", f"FDIC BankFind Suite API {API} (Call Report data, all FDIC-insured institutions), summed by quarter (agg_by=REPDTE). Field definitions: {data['source']['fields']}"),
             ("Generated (UTC)", data["generated_utc"]), ("Latest quarter", data["latest_quarter"]),
             ("Universe", "Excludes insured U.S. branches of foreign banks (IBA=0), as in the QBP. Industry ROA/NIM/leverage match the published QBP within ~1-3bp."),
             ("Community banks", "FDIC community bank flag (CB=1), per quarter."),
             ("$10B-$250B", "Bank-level (not holding company) total assets each quarter; not inflation-adjusted; membership changes over time."),
             ("Averages", "avg X = (X at prior quarter-end + X at current quarter-end) / 2. Quarterly flows annualized x4."),
             ("Units", "Metrics in %. Raw sheets in $ thousands.")] + [(m["title"], m["note"]) for m in data["metrics"]] + [
             ("Recession shading", "NBER: Mar-Nov 2001, Dec 2007-Jun 2009, Feb-Apr 2020."),
             ("Caveats", "Data as currently reported (amendments included). Q1 2010 FAS 166/167 consolidation and 2020-23 CECL adoption shift loans/reserves.")]
    tmp = OUT_XLSX + ".tmp.xlsx"
    with pd.ExcelWriter(tmp, engine="openpyxl") as w:
        frame("all").round(4).to_excel(w, sheet_name="Metrics_All")
        frame("cb").round(4).to_excel(w, sheet_name="Metrics_CommunityBanks")
        frame("mid").round(4).to_excel(w, sheet_name="Metrics_10B-250B")
        rawf(raw["all"]).to_excel(w, sheet_name="Raw_All")
        rawf(raw["cb"]).to_excel(w, sheet_name="Raw_CommunityBanks")
        rawf(raw["mid"]).to_excel(w, sheet_name="Raw_10B-250B")
        rawf(raw["cet1"]).to_excel(w, sheet_name="Raw_CET1_RWAreporters")
        pd.DataFrame(notes, columns=["Item", "Definition / note"]).to_excel(w, sheet_name="Notes", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 14 if ws.title != "Notes" else (34 if col[0].column_letter == "A" else 140)
            ws.freeze_panes = "C2" if ws.title != "Notes" else "A2"
    os.replace(tmp, OUT_XLSX)
    print(f"Wrote {OUT_XLSX}")


if __name__ == "__main__":
    sys.exit(main())
