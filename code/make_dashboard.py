"""Build the single-file dashboard: output/index.html.

Everything (data, chart library, styles) is inlined, so the file opens
offline and can be served as-is from GitHub Pages.

Run:  python make_dashboard.py
"""

import json

import config as C


def main():
    data = (C.OUTPUT_DIR / "report_data.json").read_text()
    author = json.loads(data)["author"]
    as_of = json.loads(data)["as_of"]
    page = (C.TEMPLATE_DIR / "dashboard.html").read_text()
    chart_js = (C.ASSET_DIR / "chart.umd.min.js").read_text()
    page = (page.replace("__CHART__", chart_js).replace("__DATA__", data)
                .replace("__AUTHOR__", author).replace("__ASOF__", as_of))
    out = C.OUTPUT_DIR / "index.html"
    out.write_text(page)
    print(f"Dashboard written to {out} ({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()
