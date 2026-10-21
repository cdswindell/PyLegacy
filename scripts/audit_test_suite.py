"""Opt-in, bounded fresh-process pytest profiling; never loaded by default."""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from statistics import median
from typing import Any

import pytest


_DATA: dict[str, Any] = {"cases": [], "fixtures": {}, "phases": [], "fixture_setups": [], "collection_errors": []}
_RANKINGS = (
    ("Individual phases", lambda phase: phase["id"] + " (" + phase["phase"] + ")", 25),
    ("Individual cases", lambda phase: phase["id"], 25),
    ("Modules", lambda phase: phase["id"].split("::")[0], None),
    ("Parameter families", lambda phase: phase["id"].split("[", 1)[0], 25),
    ("Setup phases", lambda phase: phase["id"] if phase["phase"] == "setup" else None, 25),
    ("Call phases", lambda phase: phase["id"] if phase["phase"] == "call" else None, 25),
    ("Teardown phases", lambda phase: phase["id"] if phase["phase"] == "teardown" else None, 25),
)


def pytest_collection_finish(session):
    for item in session.items:
        fixtures = {}
        # Pytest has no public API exposing resolved fixture definitions.
        # noinspection PyProtectedMember
        for name, definitions in item._fixtureinfo.name2fixturedefs.items():
            if definitions:
                definition = definitions[-1]
                key = f"{name}:{definition.func.__code__.co_filename}:{definition.func.__code__.co_firstlineno}"
                fixtures[name] = key
                _DATA["fixtures"][key] = {
                    "scope": definition.scope,
                    "source": str(Path(definition.func.__code__.co_filename)),
                    "line": definition.func.__code__.co_firstlineno,
                }
        _DATA["cases"].append(
            {
                "id": item.nodeid,
                "source": item.location,
                "fixtures": fixtures,
                "parameters": {
                    key: repr(value)
                    if type(value) in (str, int, float, bool, bytes, type(None))
                    else type(value).__qualname__
                    for key, value in item.callspec.params.items()
                }
                if hasattr(item, "callspec")
                else {},
                "marks": [mark.name for mark in item.iter_markers()],
            }
        )


@pytest.hookimpl(wrapper=True)
def pytest_fixture_setup(fixturedef, request):
    start = time.perf_counter()
    try:
        return (yield)
    finally:
        _DATA["fixture_setups"].append(
            {
                "name": fixturedef.argname,
                "scope": fixturedef.scope,
                "node": request.node.nodeid,
                "source": fixturedef.func.__code__.co_filename,
                "seconds": time.perf_counter() - start,
            }
        )


def pytest_runtest_logreport(report):
    _DATA["phases"].append(
        {
            "id": report.nodeid,
            "phase": report.when,
            "seconds": report.duration,
            "outcome": report.outcome,
            "message": str(report.longrepr) if report.longrepr else None,
        }
    )


def pytest_collectreport(report):
    if report.failed:
        _DATA["collection_errors"].append({"id": report.nodeid, "message": str(report.longrepr)})


def pytest_sessionfinish(session, exitstatus):
    _DATA["exitstatus"] = int(exitstatus)
    _DATA["plugins"] = sorted(
        (distribution.project_name, distribution.version)
        for _, distribution in session.config.pluginmanager.list_plugin_distinfo()
    )
    Path(os.environ["PYTRAIN_AUDIT_OUTPUT"]).write_text(json.dumps(_DATA, indent=2) + "\n")


def read_evidence(path):
    if path.exists():
        return json.loads(path.read_text())
    with gzip.open(str(path) + ".gz", "rt") as stream:
        return json.load(stream)


def summarize(directory, prefix, destination, plain=False):
    processes = [read_evidence(directory / f"{prefix}-{index}-process.json") for index in (1, 2, 3)]
    if any(process["status"] != 0 for process in processes):
        raise ValueError("All three runs must finish successfully")
    walls = [process["wall_seconds"] for process in processes]
    summary = {"runs": prefix, "wall_seconds": {"median": median(walls), "min": min(walls), "max": max(walls)}}
    if plain:
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
        return
    runs = [read_evidence(directory / f"{prefix}-{index}.json") for index in (1, 2, 3)]
    cases = runs[0]["cases"]
    if not all([case["id"] for case in run["cases"]] == [case["id"] for case in cases] for run in runs):
        raise ValueError("Collected node IDs differ across runs")
    modules = sorted({case["id"].split("::")[0] for case in cases})
    root = Path(__file__).resolve().parents[1]
    inventory = [
        "# Complete collected-family inventory",
        "",
        f"Generated from three {prefix} runs; no current source files are read.",
        "",
        f"Expanded cases and fixture definitions can be regenerated in `{prefix}-1.json.gz` with the runner.",
        "Source provenance is captured at run time in process metadata, not reconstructed during summarization.",
        "Numbers below count collected cases, not loop iterations. Source lines are one-based.",
        "",
    ]
    for module in modules:
        selected = [case for case in cases if case["id"].split("::")[0] == module]
        families = defaultdict(list)
        for case in selected:
            families[case["id"].split("[", 1)[0]].append(case)
        inventory.extend(
            [
                f"## {module}",
                "",
                f"{len(selected)} cases; {len(families)} families. Retain unless mapped to a survivor in the main report.",
                "",
                "| Family | Cases | Fixture closure |",
                "|---|---:|---|",
            ]
        )
        for family, members in families.items():
            names = sorted({name for member in members for name in member["fixtures"]})
            inventory.append(f"| `{family.split('::', 1)[1]}` | {len(members)} | {', '.join(names)} |")
        inventory.append("")
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (destination / "inventory.md").write_text("\n".join(inventory) + "\n")
    lines = [
        "# Measured rankings",
        "",
        "Seconds; median across three runs. Module/family totals include setup, call, and teardown.",
        "",
    ]
    for title, key, limit in _RANKINGS:
        totals = []
        for run in runs:
            values = defaultdict(float)
            for phase in run["phases"]:
                bucket = key(phase)
                if bucket is not None:
                    values[bucket] += phase["seconds"]
            totals.append(values)
        ranking = sorted(((median(total[name] for total in totals), name) for name in totals[0]), reverse=True)
        lines.extend([f"## {title}", "", "| Item | Median | Min | Max |", "|---|---:|---:|---:|"])
        for value, name in ranking[:limit]:
            values = [total[name] for total in totals]
            lines.append(f"| `{name}` | {float(value):.6f} | {float(min(values)):.6f} | {float(max(values)):.6f} |")
        lines.append("")
    lines.extend(
        [
            "## Fixture setup totals",
            "",
            "Exclusive of dependency setup; includes fixture hook overhead. Finalizers are attributed only to case teardown, not individual fixtures.",
            "",
            "| Fixture (source) | Invocations/run | Median total |",
            "|---|---:|---:|",
        ]
    )
    fixture_totals = []
    counts = Counter()
    for run in runs:
        values = defaultdict(float)
        for event in run["fixture_setups"]:
            name = event["name"] + " (" + event["source"].replace(str(root) + "/", "") + ")"
            values[name] += event["seconds"]
            if run is runs[0]:
                counts[name] += 1
        fixture_totals.append(values)
    for value, name in sorted(
        ((median(total[name] for total in fixture_totals), name) for name in fixture_totals[0]), reverse=True
    ):
        lines.append(f"| `{name}` | {counts[name]} | {float(value):.6f} |")
    (destination / "rankings.md").write_text("\n".join(lines) + "\n")
    print(f"Modules: {len(modules)}; cases: {len(cases)}; fixtures: {len(runs[0]['fixtures'])}")
    for index, run in enumerate(runs, 1):
        totals = defaultdict(float)
        for phase in run["phases"]:
            totals[phase["phase"]] += phase["seconds"]
        print(index, dict(totals), "plugins", run["plugins"])
    print("Skipped cases:")
    for phase in runs[0]["phases"]:
        if phase["outcome"] == "skipped":
            print(phase["id"], phase["message"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", nargs="?", help="Unique output name (existing evidence is not overwritten)")
    parser.add_argument("--runs", help="Prefix of three profiled runs to summarize")
    parser.add_argument("--output-dir", type=Path, default=Path("doc/test-suite-audit-data/raw"))
    parser.add_argument("--report-dir", type=Path, help="New directory for derived reports")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--plain", action="store_true", help="Do not load the profiling plugin")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if args.summarize:
        if not args.runs or not args.report_dir:
            parser.error("--summarize requires --runs and --report-dir (a new directory)")
        try:
            summarize(directory, args.runs, args.report_dir, args.plain)
        except (OSError, ValueError) as error:
            parser.error(f"Cannot summarize evidence: {error}")
        return 0
    if not args.label or Path(args.label).name != args.label:
        parser.error("A simple run label is required")
    output = directory / f"{args.label}.json"
    log = directory / f"{args.label}.log"
    metadata = directory / f"{args.label}-process.json"
    if any(path.exists() or Path(str(path) + ".gz").exists() for path in (output, log, metadata)):
        parser.error("Choose a new label; evidence already exists")
    command = [sys.executable, "-m", "pytest", "--durations=0", "--durations-min=0"]
    if args.collect_only:
        command.append("--collect-only")
    if not args.plain:
        command.extend(["-p", "scripts.audit_test_suite"])
    environment = dict(os.environ, PYTRAIN_AUDIT_OUTPUT=str(output))
    start = time.perf_counter()
    with log.open("w") as stream:
        try:
            result = subprocess.run(
                command, cwd=root, env=environment, stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout
            )
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = "timeout"
    details = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "module_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / "tests").rglob("*.py"))
        },
        "command": command,
        "wall_seconds": time.perf_counter() - start,
        "status": status,
        "timeout_seconds": args.timeout,
        "python": sys.version,
        "platform": platform.platform(),
        "environment": {
            name: os.environ.get(name)
            for name in (
                "PYTEST_ADDOPTS",
                "PYTEST_PLUGINS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "PYTRAIN_API_CHECKOUT",
                "PYTHONPATH",
            )
        },
    }
    metadata.write_text(json.dumps(details, indent=2) + "\n")
    print(json.dumps(details, indent=2))
    if output.exists():
        data = json.loads(output.read_text())
        print(f"Collected: {len(data['cases'])}; phase outcomes:")
        print(Counter((phase["phase"], phase["outcome"]) for phase in data["phases"]))
        for phase in data["phases"] + data["collection_errors"]:
            if phase.get("outcome") == "failed" or phase in data["collection_errors"]:
                print(phase["id"], phase["message"])
    for path in (output, log):
        if path.exists():
            with gzip.open(str(path) + ".gz", "wb") as stream:
                stream.write(path.read_bytes())
            path.unlink()
    return 0 if status == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
