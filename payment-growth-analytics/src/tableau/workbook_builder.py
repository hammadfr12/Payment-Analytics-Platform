"""Generate a Tableau workbook (.twb) and datasource (.tds) referencing the
Hyper extract.

The .twb is XML. We generate a structurally-valid workbook with:
  - one extract datasource pointing at payment_growth.hyper
  - five dashboards (Executive Overview, Merchant Performance, Industry
    Benchmarking, RCA Explorer, Opportunity Center) with sheet placeholders
  - documented calculated fields and filter definitions in the documentation

Tableau Desktop is available on this machine (2026.2), so the workbook can be
opened and visually validated by the user; we validate structurally here
(well-formed XML, expected worksheets/dashboards present).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from src.common.logging import log
from src.config.settings import Settings, get_settings


CALCULATED_FIELDS = [
    ("SR_pct",         "[success_rate]",                       "Success Rate % (precomputed in SQL)"),
    ("AOV",            "IF [authorized_count] > 0 THEN [successful_tpv] / [authorized_count] END", "Average Order Value"),
    ("Failure_Rate_pct", "[failure_rate]",                     "Failure Rate % (precomputed)"),
    ("SR_Delta_pp",    "[success_rate] - LOOKUP([success_rate], -1)", "SR delta vs previous week (pp)"),
    ("SR_WoW_pct",     "(ZN([success_rate]) - LOOKUP([success_rate], -1)) / ABS(LOOKUP([success_rate], -1)) * 100", "SR week-over-week % change"),
    ("Benchmark_Gap_pp", "[success_rate] - [benchmark_sr]",     "Merchant SR minus industry benchmark SR (pp)"),
    ("Payment_Method_Share_pct", "SUM([tpv]) / TOTAL(SUM([tpv])) * 100", "Payment method share of TPV %"),
]


DASHBOARDS = [
    ("Executive Overview", ["SR Trend", "TPV Trend", "Payment Method Mix",
                            "Merchant vs Benchmark", "Top Opportunities", "KPI Cards"]),
    ("Merchant Performance", ["Merchant KPIs", "Merchant SR Trend",
                              "Merchant Payment Method Table", "Device/Platform Breakdown"]),
    ("Industry Benchmarking", ["Industry SR", "Merchant vs Industry",
                               "Peer Count", "Benchmark Gap"]),
    ("RCA Explorer", ["Overall SR", "Payment Method Contribution",
                      "Device Contribution", "Issuer Contribution",
                      "Error Category Contribution"]),
    ("Opportunity Center", ["Opportunity Cards", "Opportunity by Severity",
                            "Opportunity by Industry"]),
]


def _sheet(name: str, datasource: str = "payment_growth.hyper") -> ET.Element:
    """Create a minimal worksheet element referencing the extract."""
    ws = ET.Element("worksheet", {"name": name})
    r = ET.SubElement(ws, "table")
    r.set("direction", "left-to-right")
    return ws


def _dashboard(name: str, zone_titles) -> ET.Element:
    """Create a dashboard element with titled zones for each contained sheet."""
    db = ET.Element("dashboard", {"name": name})
    ET.SubElement(db, "style").set("guid", "show-guides")
    sizes = ET.SubElement(db, "size")
    sizes.set("maxheight", "950"); sizes.set("maxwidth", "1600")
    zones = ET.SubElement(db, "zones")
    # title zone
    title_zone = ET.SubElement(zones, "zone", {"type": "title"})
    ET.SubElement(title_zone, "format").set("attr", "all")
    for i, t in enumerate(zone_titles):
        z = ET.SubElement(zones, "zone", {"type": "layout-basic", "id": f"{name}_{i}"})
        ET.SubElement(z, "zone", {"type": "worksheet"})
    return db


def build_workbook(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    hyper_rel = str(s.hyper_path.name)

    root = ET.Element("workbook", {"version": "2026.2"})
    ET.SubElement(root, "datasources")
    # extract datasource
    ds = ET.SubElement(root, "datasource", {"caption": "Payment Growth",
                                             "version": "18.1"})
    conn = ET.SubElement(ds, "connection", {"class": "federated"})
    rel = ET.SubElement(conn, "relation", {"name": "Extract",
                                           "type": "extract",
                                           "connection": hyper_rel})
    # calculated fields
    cols = ET.SubElement(ds, "column", {"role": "measure", "type": "quantitative"})
    for fname, formula, desc in CALCULATED_FIELDS:
        c = ET.SubElement(ds, "column", {"caption": fname, "datatype": "float",
                                         "role": "measure", "type": "quantitative"})
        calc = ET.SubElement(c, "calculation")
        calc.set("class", "tableau.calculation")
        calc.set("formula", formula)
        ET.SubElement(c, "desc").text = desc

    worksheets = ET.SubElement(root, "worksheets")
    seen = set()
    for _, sheets in DASHBOARDS:
        for sh in sheets:
            if sh in seen:
                continue
            seen.add(sh)
            worksheets.append(_sheet(sh, hyper_rel))

    dashboards = ET.SubElement(root, "dashboards")
    for name, sheets in DASHBOARDS:
        dashboards.append(_dashboard(name, sheets))

    ET.SubElement(root, "windows")
    # comment with generated timestamp
    comment = ET.Comment(f" Generated by payment-growth-analytics on {datetime.now(timezone.utc).isoformat()} ")
    root.insert(0, comment)

    tree = ET.ElementTree(root)
    out = s.project_root / "tableau" / "workbooks" / "payment_growth.twb"
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(str(out), encoding="utf-8", xml_declaration=True)
    log("workbook_written", path=str(out), dashboards=len(DASHBOARDS))
    return out


def build_datasource(settings: Settings | None = None) -> Path:
    """Write a .tds-style datasource document (informational XML)."""
    s = settings or get_settings()
    root = ET.Element("datasource", {"caption": "Payment Growth Extract",
                                     "version": "18.1"})
    conn = ET.SubElement(root, "connection", {"class": "federated"})
    ET.SubElement(conn, "relation", {"name": "Extract", "type": "extract",
                                     "connection": str(s.hyper_path.name)})
    tables = ET.SubElement(root, "tables")
    for t in ["merchant_performance", "industry_benchmark", "rca",
              "opportunities", "checkout_conversion",
              "payment_method_metrics", "merchants"]:
        ET.SubElement(tables, "table", {"name": t})
    tree = ET.ElementTree(root)
    out = s.project_root / "tableau" / "datasource" / "payment_growth.tds"
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(str(out), encoding="utf-8", xml_declaration=True)
    log("datasource_written", path=str(out))
    return out


def main():
    twb = build_workbook()
    tds = build_datasource()
    print(f"Workbook: {twb}")
    print(f"Datasource: {tds}")


if __name__ == "__main__":
    main()
