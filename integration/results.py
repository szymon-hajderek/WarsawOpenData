"""Collects the metrics and checks of each scenario and writes `RESULTS.md` + `report/results.json`.

`results.json` also keeps the user tracks and detections for the replay page (git-ignored, rebuilt by a run).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
_runs: dict[str, dict] = {}


def record(scenario: str, title: str, source: str, metrics: dict, checks: list[tuple[str, bool]],
           replay: dict | None = None) -> None:
    _runs[scenario] = {"title": title, "source": source, "metrics": metrics,
                       "checks": [{"check": name, "ok": bool(ok)} for name, ok in checks], "replay": replay or {}}


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def write() -> None:
    if not _runs:
        return
    engine = os.getenv("ROUTE_ENGINE", "real")
    out = HERE / "report"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps({"engine": engine, "generated": datetime.now().isoformat(
        timespec="seconds"), "runs": _runs}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# Integration test results", "",
             f"Engine: `{engine}`. Written by `uv run pytest ../integration` (only the scenarios that ran).", ""]
    for source, heading in (("recorded", "Recorded live data"), ("gtfs", "Synthetic data from GTFS")):
        runs = {k: v for k, v in _runs.items() if v["source"] == source}
        if not runs:
            continue
        lines += [f"## {heading}", ""]
        for name, run in runs.items():
            known = sum(not c["ok"] and "(known bug:" in c["check"] for c in run["checks"])
            passed = all(c["ok"] or "(known bug:" in c["check"] for c in run["checks"])
            status = ("PASS" if passed else "FAIL") + (f", {known} known bugs" if known else "")
            lines += [f"### {run['title']} (`{name}`): {status}", "",
                      "| Metric | Value |", "|---|---|"]
            lines += [f"| {k} | {_fmt(v)} |" for k, v in run["metrics"].items()]
            lines += ["", *[f"- [{'x' if c['ok'] else ' '}] {c['check']}" for c in run["checks"]], ""]
    (HERE / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
