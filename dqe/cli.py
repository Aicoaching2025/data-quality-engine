"""Command-line interface: ``dqe assess <source>``.

Prints a colour scorecard to the terminal and writes JSON + HTML reports. Exit
code reflects the verdict (0 = ready/review, 1 = not ready) so it can gate a CI
pipeline.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dqe import __version__
from dqe.engine import QualityEngine, QualityReport
from dqe.report import write_html, write_json
from dqe.types import Status


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "assess":
        return _cmd_assess(args)
    if args.command == "list-checks":
        return _cmd_list_checks()
    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dqe",
        description="Data Quality Engine — assess dataset readiness for ML/analytics.",
    )
    parser.add_argument("--version", action="version", version=f"dqe {__version__}")
    sub = parser.add_subparsers(dest="command")

    a = sub.add_parser("assess", help="Assess a data source and write a report.")
    a.add_argument("source", help="Path to CSV/Excel/Parquet (or SQL/API with --source-type).")
    a.add_argument("--source-type", choices=["csv", "excel", "parquet", "sql", "api"],
                   help="Force the connector type (inferred from extension by default).")
    a.add_argument("--config", "-c", help="Path to a YAML/JSON config file.")
    a.add_argument("--name", "-n", help="Dataset name shown in the report.")
    a.add_argument("--out", "-o", default="reports", help="Output directory (default: reports/).")
    a.add_argument("--format", "-f", default="json,html",
                   help="Comma-separated outputs: json, html (default: both).")
    a.add_argument("--quiet", "-q", action="store_true", help="Suppress the terminal scorecard.")

    sub.add_parser("list-checks", help="List the available checks and their dimensions.")
    return parser


def _cmd_assess(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    config["_version"] = __version__
    engine = QualityEngine(config)

    try:
        report = engine.assess(
            args.source,
            source_type=args.source_type,
            dataset_name=args.name,
            reference_time=datetime.now(),
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        _error(f"{exc}")
        return 2

    formats = {f.strip().lower() for f in args.format.split(",") if f.strip()}
    out_dir = Path(args.out)
    written: list[Path] = []
    safe_name = _slugify(report.dataset_name)
    if "json" in formats:
        written.append(write_json(report, out_dir / f"{safe_name}.json"))
    if "html" in formats:
        written.append(write_html(report, out_dir / f"{safe_name}.html"))

    if not args.quiet:
        _print_scorecard(report, written)

    # Gate: fail the process if the data is not ready.
    return 0 if report.scorecard.verdict != "NOT READY" else 1


def _cmd_list_checks() -> int:
    from dqe.checks import available_checks
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="Available checks")
        table.add_column("Check", style="bold cyan")
        table.add_column("Dimension", style="magenta")
        for name, cls in sorted(available_checks().items()):
            table.add_row(name, cls.dimension.value)
        console.print(table)
    except ImportError:  # pragma: no cover - rich always installed in practice
        for name, cls in sorted(available_checks().items()):
            print(f"{name:20s} {cls.dimension.value}")
    return 0


# -- terminal rendering -----------------------------------------------------

def _print_scorecard(report: QualityReport, written: list[Path]) -> None:
    try:
        _print_rich(report, written)
    except ImportError:  # pragma: no cover
        _print_plain(report, written)


def _print_rich(report: QualityReport, written: list[Path]) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    sc = report.scorecard
    color = {"READY": "green", "REVIEW": "yellow", "NOT READY": "red"}[sc.verdict]

    header = (
        f"[bold]{report.dataset_name}[/bold]   "
        f"[{color}]{sc.verdict}[/{color}]\n"
        f"Readiness [bold {color}]{sc.overall_score:.0f}/100[/bold {color}]  "
        f"Grade [bold]{sc.grade}[/bold]   "
        f"[green]{sc.n_pass} pass[/green] | "
        f"[yellow]{sc.n_warn} warn[/yellow] | "
        f"[red]{sc.n_fail} fail[/red]"
    )
    console.print(Panel(header, title="Data Quality Engine", expand=False))

    dim_table = Table(show_header=True, header_style="bold")
    dim_table.add_column("Dimension")
    dim_table.add_column("Score", justify="right")
    dim_table.add_column("P/W/F", justify="right")
    for d in sc.dimensions:
        dc = "green" if d.score >= 90 else ("yellow" if d.score >= 75 else "red")
        dim_table.add_row(
            d.dimension.value.capitalize(),
            f"[{dc}]{d.score:.0f}[/{dc}]",
            f"{d.n_pass}/{d.n_warn}/{d.n_fail}",
        )
    console.print(dim_table)

    findings = report.findings
    if findings:
        console.print("\n[bold]Top findings[/bold]")
        for f in findings[:8]:
            mark = "[red]FAIL[/red]" if f.status == Status.FAIL else "[yellow]WARN[/yellow]"
            console.print(f"  {mark}  {f.message}")
        if len(findings) > 8:
            console.print(f"  [dim]... and {len(findings) - 8} more (see report)[/dim]")
    else:
        console.print("\n[green]All checks passed.[/green]")

    if written:
        console.print("\n[dim]Reports written:[/dim]")
        for p in written:
            console.print(f"  [cyan]{p}[/cyan]")


def _print_plain(report: QualityReport, written: list[Path]) -> None:
    sc = report.scorecard
    print(f"\n{report.dataset_name} — {sc.verdict}")
    print(f"Readiness {sc.overall_score:.0f}/100  Grade {sc.grade}  "
          f"({sc.n_pass} pass / {sc.n_warn} warn / {sc.n_fail} fail)")
    for d in sc.dimensions:
        print(f"  {d.dimension.value:14s} {d.score:5.0f}")
    for p in written:
        print(f"report: {p}")


# -- helpers ----------------------------------------------------------------

def _load_config(path: Optional[str]) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        _error(f"Config file not found: {p}")
        raise SystemExit(2)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(text) or {}
    import json
    return json.loads(text)


def _slugify(name: str) -> str:
    keep = "-_."
    return "".join(c if c.isalnum() or c in keep else "_" for c in name).strip("_") or "dataset"


def _error(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
