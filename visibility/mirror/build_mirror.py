"""StatCan mirror-experiment page builder.

Reads visibility/mirror/manifest.yaml, fetches each TREATMENT table's view
data from StatCan WDS (getCubeMetadata + getDataFromCubePidCoordAndLatestNPeriods),
and renders static, crawlable HTML pages — values in the markup, schema.org/Dataset
JSON-LD, prominent Statistics Canada attribution — into tables/ at the repo root,
plus tables/index.html and sitemap.xml.

Run: python visibility/mirror/build_mirror.py
Control tables in the manifest are never fetched or rendered.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
META_CACHE = ROOT / "visibility" / "cache" / "mirror_meta"
OUT_DIR = ROOT / "tables"
BASE_URL = "https://p3ji.github.io/stats/"

WDS = "https://www150.statcan.gc.ca/t1/wds/rest"
BATCH = 50

MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# ── WDS helpers ───────────────────────────────────────────────────────────

def get_metadata(pid: str) -> dict:
    cached = META_CACHE / f"{pid}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    resp = requests.post(f"{WDS}/getCubeMetadata", json=[{"productId": int(pid)}], timeout=60)
    resp.raise_for_status()
    payload = resp.json()[0]
    if payload.get("status") != "SUCCESS":
        raise RuntimeError(f"getCubeMetadata failed for {pid}: {str(payload)[:200]}")
    META_CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(payload["object"]), encoding="utf-8")
    return payload["object"]


def get_code_sets() -> dict:
    cached = META_CACHE / "code_sets.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    resp = requests.get(f"{WDS}/getCodeSets", timeout=60)
    resp.raise_for_status()
    obj = resp.json()["object"]
    META_CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(obj), encoding="utf-8")
    return obj


def fetch_coords(pid: str, coords: list[str], latest_n: int) -> dict[str, list[dict]]:
    """Fetch data points for a list of coordinates. Returns {coordinate: [datapoints]}."""
    out: dict[str, list[dict]] = {}
    for i in range(0, len(coords), BATCH):
        batch = coords[i:i + BATCH]
        body = [{"productId": int(pid), "coordinate": c, "latestN": latest_n} for c in batch]
        resp = requests.post(f"{WDS}/getDataFromCubePidCoordAndLatestNPeriods", json=body, timeout=120)
        resp.raise_for_status()
        for item in resp.json():
            if item.get("status") != "SUCCESS":
                raise RuntimeError(f"data fetch failed for {pid}: {str(item)[:300]}")
            obj = item["object"]
            out[obj["coordinate"]] = obj["vectorDataPoint"]
    return out


# ── manifest resolution ───────────────────────────────────────────────────

class Cube:
    def __init__(self, pid: str, meta: dict):
        self.pid = pid
        self.meta = meta
        self.dims = meta["dimension"]  # ordered by dimensionPositionId
        self.by_name = {d["dimensionNameEn"]: d for d in self.dims}

    def dim(self, name: str) -> dict:
        if name not in self.by_name:
            raise KeyError(f"{self.pid}: no dimension named {name!r}; have {list(self.by_name)}")
        return self.by_name[name]

    def member(self, dim_name: str, member_name: str) -> dict:
        d = self.dim(dim_name)
        for m in d["member"]:
            if m["memberNameEn"].strip() == member_name.strip():
                return m
        # tolerate truncated manifest names (metadata names can be very long)
        matches = [m for m in d["member"] if m["memberNameEn"].strip().startswith(member_name.strip()[:60])]
        if len(matches) == 1:
            return matches[0]
        raise KeyError(f"{self.pid}: no member {member_name!r} in dim {dim_name!r}; "
                       f"have {[m['memberNameEn'][:60] for m in d['member']][:30]}")

    def members(self, dim_name: str, spec) -> list[dict]:
        if spec == "all":
            return list(self.dim(dim_name)["member"])
        return [self.member(dim_name, n) for n in spec]

    def coordinate(self, member_by_dim: dict[str, int]) -> str:
        """member_by_dim: {dimensionNameEn: memberId} → 10-part coordinate string."""
        parts = []
        for d in sorted(self.dims, key=lambda d: d["dimensionPositionId"]):
            parts.append(str(member_by_dim.get(d["dimensionNameEn"], 0)))
        while len(parts) < 10:
            parts.append("0")
        return ".".join(parts)


def format_pid(pid: str) -> str:
    return f"{pid[:2]}-{pid[2:4]}-{pid[4:8]}-01"


def canonical_url(pid: str) -> str:
    return f"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={pid}01"


def format_period(ref_per: str, frequency: int) -> str:
    d = date.fromisoformat(ref_per)
    if frequency == 6:  # monthly
        return f"{MONTHS[d.month]} {d.year}"
    if frequency == 9:  # quarterly
        return f"Q{(d.month - 1) // 3 + 1} {d.year}"
    return str(d.year)


def format_value(dp: dict, code_sets: dict) -> str:
    """Format one datapoint: number with separators/decimals, or its status symbol."""
    value = dp.get("value")
    if value is None:
        status = dp.get("statusCode")
        for s in code_sets.get("status", []):
            if s.get("statusCode") == status:
                return s.get("statusRepresentationEn") or ".."
        return ".."
    decimals = dp.get("decimals", 0) or 0
    text = f"{value:,.{decimals}f}"
    symbol = dp.get("symbolCode")
    if symbol:
        for s in code_sets.get("symbol", []):
            if s.get("symbolCode") == symbol:
                rep = s.get("symbolRepresentationEn")
                if rep:
                    text += f"<sup>{html.escape(rep)}</sup>"
    return text


def uom_label(member: dict, code_sets: dict) -> str | None:
    code = member.get("memberUomCode")
    if code is None:
        return None
    for u in code_sets.get("uom", []):
        if u.get("memberUomCode") == code:
            return u.get("memberUomEn")
    return None


def scalar_label(code: int, code_sets: dict) -> str | None:
    if not code:
        return None
    for s in code_sets.get("scalar", []):
        if s.get("scalarFactorCode") == code:
            return s.get("scalarFactorDescEn")
    return None


# ── view rendering ────────────────────────────────────────────────────────

def build_view(cube: Cube, view: dict, code_sets: dict) -> dict:
    """Fetch a view's data and return a render-ready grid.

    Returns {title, caption, col_headers, rows: [(label, [cell_html])],
             notes: [...], grid: {(row_label, col_label): datapoint}}.
    """
    fixed = {name: cube.member(name, mname)["memberId"]
             for name, mname in (view.get("fixed") or {}).items()}
    latest_n = view.get("latestN", 1)
    freq = cube.meta.get("frequencyCode", 12)

    rows_spec, cols_spec = view["rows"], view["cols"]
    time_rows = rows_spec == "time"
    value_cols = cols_spec == "value"

    row_members = None if time_rows else cube.members(rows_spec["dim"], rows_spec["members"])
    col_members = None if (value_cols or cols_spec == "time") else cube.members(cols_spec["dim"], cols_spec["members"])

    # enumerate coordinates: cross product of (row members x col members),
    # where a "time"/"value" axis contributes nothing to the coordinate
    coords: dict[tuple[str, str], str] = {}
    row_axis = [(m["memberNameEn"], {rows_spec["dim"]: m["memberId"]}) for m in row_members] if row_members else [("", {})]
    col_axis = [(m["memberNameEn"], {cols_spec["dim"]: m["memberId"]}) for m in col_members] if col_members else [("", {})]
    for r_label, r_sel in row_axis:
        for c_label, c_sel in col_axis:
            coords[(r_label, c_label)] = cube.coordinate({**fixed, **r_sel, **c_sel})

    data = fetch_coords(cube.pid, list(dict.fromkeys(coords.values())), latest_n)

    scalars: set[int] = set()
    for dps in data.values():
        for dp in dps:
            if dp.get("value") is not None:
                scalars.add(dp.get("scalarFactorCode", 0) or 0)

    def latest(dps: list[dict]) -> dict | None:
        return max(dps, key=lambda dp: dp["refPer"]) if dps else None

    # column headers, annotated with unit of measure where it lives on members
    def annotate(members: list[dict] | None, labels: list[str]) -> list[str]:
        if not members:
            return labels
        out = []
        for m, label in zip(members, labels):
            uom = uom_label(m, code_sets)
            out.append(f"{label} ({uom})" if uom and uom.lower() not in label.lower() else label)
        return out

    rows_out: list[tuple[str, list[str]]] = []
    periods_seen: set[str] = set()

    if time_rows:
        # rows = periods (newest first), cols = col members
        col_labels = annotate(col_members, [m["memberNameEn"] for m in col_members])
        series = {c_label: data[coords[("", c_label)]] for c_label, _ in col_axis}
        all_periods = sorted({dp["refPer"] for dps in series.values() for dp in dps}, reverse=True)
        for per in all_periods:
            cells = []
            for c_label, _ in col_axis:
                dp = next((d for d in series[c_label] if d["refPer"] == per), None)
                cells.append(format_value(dp, code_sets) if dp else "..")
            rows_out.append((format_period(per, freq), cells))
            periods_seen.add(per)
        col_headers = col_labels
    else:
        if value_cols:
            uoms = {uom_label(m, code_sets) for m in row_members} - {None}
            col_headers = [uoms.pop() if len(uoms) == 1 else "Value"]
        else:
            col_headers = annotate(col_members, [m["memberNameEn"] for m in col_members])
        for r_label, _ in row_axis:
            cells = []
            for c_label, _ in col_axis:
                dp = latest(data[coords[(r_label, c_label)]])
                cells.append(format_value(dp, code_sets) if dp else "..")
                if dp:
                    periods_seen.add(dp["refPer"])
            rows_out.append((r_label, cells))

    notes = []
    scalar_names = sorted(filter(None, (scalar_label(s, code_sets) for s in scalars)))
    if scalar_names:
        notes.append("Values expressed in " + " / ".join(n.lower() for n in scalar_names) + ".")
    if periods_seen:
        span = sorted(periods_seen)
        label = format_period(span[-1], freq) if span[0] == span[-1] else \
            f"{format_period(span[0], freq)} to {format_period(span[-1], freq)}"
        notes.append(f"Reference period: {label}.")

    # keep raw latest datapoints for headline resolution
    grid = {}
    for (r_label, c_label), coord in coords.items():
        dp = latest(data[coord])
        if dp:
            grid[(r_label, c_label)] = dp

    return {"title": view["title"], "caption": view.get("caption"),
            "col_headers": col_headers, "rows": rows_out, "notes": notes,
            "grid": grid, "freq": freq}


def resolve_headline(spec: dict, views: dict[str, dict], code_sets: dict) -> str | None:
    if not spec:
        return None
    view = views[spec["view"]]
    col = "" if spec.get("col") == "value" else spec.get("col", "")
    if spec.get("row_period") == "latest":
        # time-rows view: pick the newest datapoint in the named column member
        cands = [(r, c) for (r, c) in view["grid"] if col in (c, "")]
        key = max(cands, key=lambda k: view["grid"][k]["refPer"])
    else:
        # member names in headline specs may be truncated versions of very long labels
        key = next((r, c) for (r, c) in view["grid"]
                   if r.startswith(spec["row"][:60]) and (c == col or col in c))
    dp = view["grid"][key]
    value = format_value(dp, code_sets)
    period = format_period(dp["refPer"], view["freq"])
    return spec["template"].format(value=value, period=period)


# ── page rendering ────────────────────────────────────────────────────────

PAGE_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  max-width:60rem;margin:0 auto;padding:1rem 1.25rem 3rem;color:#1a1a1a;background:#fff;line-height:1.5}
a{color:#26374a}
h1{font-size:1.5rem;line-height:1.3;margin-bottom:.25rem}
h2{font-size:1.15rem;margin-top:2rem;border-bottom:2px solid #26374a;padding-bottom:.25rem}
.attribution{background:#f5f6f7;border-left:4px solid #26374a;padding:.75rem 1rem;margin:1rem 0;font-size:.92rem}
.headline{font-size:1.1rem;font-weight:600;margin:1rem 0}
.caption{color:#444;font-size:.92rem;margin:.25rem 0 .75rem}
table{border-collapse:collapse;width:100%;margin:.5rem 0 1rem;font-size:.92rem;font-variant-numeric:tabular-nums}
caption{text-align:left;font-weight:600;padding:.25rem 0}
th,td{border:1px solid #d5d8dc;padding:.35rem .6rem;text-align:right}
th:first-child,td:first-child{text-align:left}
thead th{background:#eef1f4}
tbody tr:nth-child(even){background:#fafbfc}
.notes{font-size:.85rem;color:#555}
footer{margin-top:2.5rem;border-top:1px solid #d5d8dc;padding-top:.75rem;font-size:.85rem;color:#555}
""".strip()


def render_page(pid: str, cfg: dict, cube: Cube, views: dict[str, dict],
                headline: str | None, built: str) -> str:
    fp = format_pid(pid)
    canon = canonical_url(pid)
    title = cfg["page_title"]
    cube_title = cube.meta["cubeTitleEn"]
    page_url = f"{BASE_URL}tables/{cfg['slug']}.html"
    esc = html.escape

    description = (headline or f"Data from Statistics Canada table {fp}.") + \
        f" Source: Statistics Canada, Table {fp} ({cube_title})."

    json_ld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{cube_title} — Statistics Canada Table {fp}",
        "description": description,
        "url": page_url,
        "sameAs": canon,
        "isBasedOn": canon,
        "identifier": [f"Statistics Canada Table {fp}", f"PID {pid}"],
        "license": "https://www.statcan.gc.ca/en/reference/licence",
        "creator": {"@type": "Organization", "name": "Statistics Canada",
                    "url": "https://www.statcan.gc.ca/"},
        "spatialCoverage": "Canada",
        "temporalCoverage": f"{cube.meta.get('cubeStartDate', '')[:4]}/{cube.meta.get('cubeEndDate', '')[:4]}",
        "dateModified": cube.meta.get("cubeEndDate", ""),
    }

    sections = []
    for v in views.values():
        head = "".join(f"<th scope='col'>{esc(h)}</th>" for h in v["col_headers"])
        body = "".join(
            "<tr><td>" + esc(label) + "</td>" +
            "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"
            for label, cells in v["rows"])
        caption = f"<p class='caption'>{esc(v['caption'])}</p>" if v.get("caption") else ""
        notes = "".join(f"<p class='notes'>{esc(n)}</p>" for n in v["notes"])
        sections.append(
            f"<section><h2>{esc(v['title'])}</h2>{caption}"
            f"<table><thead><tr><th scope='col'></th>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table>{notes}</section>")

    headline_html = f"<p class='headline'>{esc(headline)}</p>" if headline else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — Statistics Canada Table {fp} (data mirror)</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{page_url}">
<script type="application/ld+json">{json.dumps(json_ld, indent=1)}</script>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>{esc(title)}</h1>
<p class="notes">Statistics Canada, Table {fp}: <em>{esc(cube_title)}</em></p>
<div class="attribution">
<strong>Source: <a href="{canon}">Statistics Canada, Table {fp}</a>.</strong>
This page is an independent, machine-readable mirror of the table's key figures,
reproduced under the <a href="https://www.statcan.gc.ca/en/reference/licence">Statistics
Canada Open Licence</a>. It is not affiliated with or endorsed by Statistics Canada.
For the full table, all breakdowns, and the latest data, use the
<a href="{canon}">official interactive table</a>.
</div>
{headline_html}
{"".join(sections)}
<footer>
<p>Retrieved from the Statistics Canada Web Data Service on {built}.
Values are reproduced as published, without transformation.</p>
<p><a href="index.html">All mirrored tables</a> ·
<a href="https://github.com/p3ji/stats">About this project</a> —
part of a study of how search and AI answer engines use official statistics.</p>
</footer>
</body>
</html>
"""


def render_index(pages: list[dict], built: str) -> str:
    esc = html.escape
    items = "".join(
        f"<li><a href='{p['slug']}.html'>{esc(p['title'])}</a> — "
        f"Statistics Canada Table {p['fp']}</li>"
        for p in pages)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Statistics Canada data tables — crawlable mirror</title>
<meta name="description" content="Static, machine-readable mirrors of selected Statistics Canada data tables: wages, charitable giving, volunteering, time use, and business AI adoption.">
<link rel="canonical" href="{BASE_URL}tables/">
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>Statistics Canada data tables — crawlable mirror</h1>
<div class="attribution">
Static mirrors of selected <a href="https://www150.statcan.gc.ca/t1/en/type/data">Statistics
Canada data tables</a>, reproduced under the
<a href="https://www.statcan.gc.ca/en/reference/licence">Statistics Canada Open Licence</a>.
Not affiliated with or endorsed by Statistics Canada. Published as part of a
<a href="https://github.com/p3ji/stats">study</a> of whether making official
table values crawlable changes how search and AI answer engines cite them.
</div>
<ul>{items}</ul>
<footer><p>Built {built}. <a href="../">Open Stats Lab home</a> · <a href="../benchmark/">city benchmark dashboard</a></p></footer>
</body>
</html>
"""


def render_sitemap(pages: list[dict], built_date: str) -> str:
    urls = [BASE_URL, f"{BASE_URL}benchmark/", f"{BASE_URL}tables/"] + \
        [f"{BASE_URL}tables/{p['slug']}.html" for p in pages]
    entries = "".join(
        f"<url><loc>{u}</loc><lastmod>{built_date}</lastmod></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{entries}</urlset>\n")


# ── main ──────────────────────────────────────────────────────────────────

def main() -> int:
    manifest = yaml.safe_load((HERE / "manifest.yaml").read_text(encoding="utf-8"))
    treatment = {pid for group in manifest["experiment"]["treatment"].values() for pid in group}
    code_sets = get_code_sets()
    now = datetime.now(timezone.utc)
    built = now.strftime("%Y-%m-%d")

    OUT_DIR.mkdir(exist_ok=True)
    pages = []
    for pid, cfg in manifest["tables"].items():
        if pid not in treatment:
            print(f"  skip  {pid} (control — must not be mirrored)")
            continue
        cube = Cube(pid, get_metadata(pid))
        views = {v["id"]: build_view(cube, v, code_sets) for v in cfg["views"]}
        headline = resolve_headline(cfg.get("headline"), views, code_sets)
        page = render_page(pid, cfg, cube, views, headline, built)
        (OUT_DIR / f"{cfg['slug']}.html").write_text(page, encoding="utf-8")
        pages.append({"slug": cfg["slug"], "title": cfg["page_title"], "fp": format_pid(pid)})
        print(f"  ok    {pid} -> tables/{cfg['slug']}.html   {headline!r}")

    (OUT_DIR / "index.html").write_text(render_index(pages, built), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(render_sitemap(pages, built), encoding="utf-8")
    print(f"\nWrote {len(pages)} table pages + tables/index.html + sitemap.xml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
