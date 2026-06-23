"""Serialise a :class:`QualityReport` to JSON and a standalone HTML report.

The HTML is fully self-contained — inline CSS, inline SVG charts, no CDN or JS
dependency — so it opens anywhere and screenshots cleanly for sharing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from dqe.engine import QualityReport

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Colour tokens reused by both the badges and the SVG donut.
_STATUS_COLORS = {"pass": "#1a9c5b", "warn": "#c8860d", "fail": "#d23f3f"}


def write_json(report: QualityReport, path: str | Path) -> Path:
    """Write the machine-readable JSON report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
    return path


def write_html(report: QualityReport, path: str | Path) -> Path:
    """Render and write the self-contained HTML report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(report)
    path.write_text(html, encoding="utf-8")
    return path


def render_html(report: QualityReport) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["pct"] = _pct
    env.filters["commafy"] = _commafy
    template = env.get_template("report.html.j2")
    sc = report.scorecard
    return template.render(
        report=report,
        scorecard=sc,
        profile=report.profile,
        findings=report.findings,
        results=report.results,
        score_color=_score_color(sc.overall_score),
        score_donut=_donut(sc.overall_score, _score_color(sc.overall_score)),
        status_colors=_STATUS_COLORS,
        verdict_color=_verdict_color(sc.verdict),
    )


# -- presentation helpers ---------------------------------------------------

def _score_color(score: float) -> str:
    if score >= 90:
        return _STATUS_COLORS["pass"]
    if score >= 75:
        return _STATUS_COLORS["warn"]
    return _STATUS_COLORS["fail"]


def _verdict_color(verdict: str) -> str:
    return {"READY": _STATUS_COLORS["pass"],
            "REVIEW": _STATUS_COLORS["warn"],
            "NOT READY": _STATUS_COLORS["fail"]}.get(verdict, "#666")


def _donut(score: float, color: str, radius: int = 52, stroke: int = 12) -> dict[str, Any]:
    """Geometry for an SVG progress donut (computed here to keep the template clean)."""
    import math
    circumference = 2 * math.pi * radius
    filled = circumference * (max(0.0, min(100.0, score)) / 100.0)
    return {
        "radius": radius,
        "stroke": stroke,
        "circumference": round(circumference, 2),
        "dash": f"{round(filled, 2)} {round(circumference - filled, 2)}",
        "color": color,
        "size": (radius + stroke) * 2,
        "center": radius + stroke,
    }


def _pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def _commafy(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)
