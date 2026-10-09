# FDIC Banking Dashboard

Quarterly aggregate metrics for all FDIC-insured institutions (Q1 2000 to the latest quarter), with
community banks (FDIC definition) and $10B–$250B banks alongside the industry. Same look and pipeline
as the [Financials Dashboard](https://github.com/ehines12/financials-dashboard).

Live: https://ehines12.github.io/fdic-dashboard/

* `fetch_data.py`: FDIC BankFind Suite API (`api.fdic.gov/banks/financials`, summed by quarter) to
  `web/data/data.json` and `web/data/fdic_metrics.xlsx`. If a request fails, the previous copy is kept and flagged STALE.
* `export_html.py --no-fetch --out _site/index.html`: inlines CSS/JS/Chart.js/data into one offline HTML file (+ copies the Excel file).
* `ci_summary.py`: per-group fetch status in the Actions log/job summary.
* `.github/workflows/refresh-pages.yml`: weekly (Mondays) and on demand (*Run workflow*); deploys to GitHub Pages.
* `serve.py`: local preview of `web/` at http://localhost:8010.

Metrics: ROE, ROA, NIM, efficiency ratio, provisions / loans, net charge-off rate, noncurrent loans, reserves / loans,
cost of total and interest-bearing deposits, deposit / loan / asset growth, loan-to-deposit ratio, Tier 1 leverage,
CET1 (RWA reporters, 2015+), equity / assets. Definitions are on the page and in the Excel Notes sheet.
NBER recessions shaded. Informational only; not investment advice.
