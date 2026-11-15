"""Recompute the fairness-audit recall figures from the saved reference runs (no model or network calls).

    uv run python -m tools.fairness_recall

Dev runs, from each cases.jsonl: the number of recall cases (context_recall cases with needed facts), recall, recall
found without leaking (0 for a case with a forbidden hit), Wilson 95% intervals, and needed facts found by who stated
them (the truth row's stated_by: the principal or the assistant, or anyone else). Every dev run is shown on all its
cases and, when it covers them, on the 244 case ids the Dawnmere dev runs share, so systems compare on one case set.

Test runs, from summary.json only (the test split saves no per-case records, and none are opened here): recall,
recall found without leaking taken as by_scoring.context_recall.mean_score, and intervals. That mean score is the
leak-adjusted recall when every context_recall case has needed facts (true when its n equals the recall n) and none is
an abstain case below L3, which the near-miss rule can zero; on every dev run here the two are identical. No split by
fact origin for test: it needs the per-case missing facts, which a test run does not save.
"""
import json
from pathlib import Path

from harness.report import summarize, wilson

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "results" / "reference"
SHARED = REF / "dawnmere" / "20261110T074032Z-dev-s0" / "config.json"
TEST_RUNS = ["dawnmere/20261110T161902Z-test-s0", "mem0/20261110T184704Z-test-s0"]


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _ci(ci):
    return "n/a" if ci is None else f"{100 * ci[0]:.0f}-{100 * ci[1]:.0f}%"


def _origin(v):
    return f"{v['found']}/{v['facts']} ({_pct(v['rate'])}, {_ci(v['ci95'])})"


def dev_row(name, records, facts):
    c = summarize(records, facts, {"adapter": name})["context"]
    by = c["recall_by_fact_origin"]
    return (f"| {name} | {len(records)} | {c['recall_n']} | {_pct(c['recall_mean'])} ({_ci(c['recall_ci95'])}) | "
            f"{_pct(c['recall_without_leak_mean'])} ({_ci(c['recall_without_leak_ci95'])}) | "
            f"{_origin(by['user_or_assistant'])} | {_origin(by['others'])} |")


def main():
    facts = {r["fact_id"]: r for r in map(json.loads, (ROOT / "world" / "truth.jsonl").read_text().splitlines())}
    shared = set(json.loads(SHARED.read_text())["cases"])
    head = ["| run | cases | recall n | recall (95% interval) | found without leaking (95% interval) | "
            "user or assistant facts found | other people's facts found |", "|---|---:|---:|---|---|---|---|"]
    full, common = list(head), list(head)
    for path in sorted(REF.glob("*/*/cases.jsonl")):
        name = f"{path.parent.parent.name}/{path.parent.name}"
        recs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        full.append(dev_row(name, recs, facts))
        sub = [r for r in recs if r["case_id"] in shared]
        if {r["case_id"] for r in sub} == shared:
            common.append(dev_row(name, sub, facts))
    print("## Dev, every run on all its cases\n", *full, sep="\n")
    print(f"\n## Dev, the {len(shared)} case ids the Dawnmere dev runs share\n", *common, sep="\n")
    print("\n## Test, from summary.json aggregates only\n")
    print("| run | recall n | recall (95% interval) | found without leaking (95% interval) |", "|---|---:|---|---|",
          sep="\n")
    for run in TEST_RUNS:
        s = json.loads((REF / run / "summary.json").read_text())
        cr = s["by_scoring"]["context_recall"]
        n, rec, clean = cr["n"], s["context"]["recall_mean"], cr["mean_score"]
        print(f"| {run} | {n} | {_pct(rec)} ({_ci(wilson(rec, n))}) | {_pct(clean)} ({_ci(wilson(clean, n))}) |")


if __name__ == "__main__":
    main()
