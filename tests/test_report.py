"""harness/report.py: tokens by area, sensitive facts sent, and the system's upkeep per replayed day."""
import json

from harness import report

FACTS = {"f1": {"sensitivity": ["health"], "notes": ""}, "f2": {"sensitivity": [], "notes": ""},
         "f3": {"sensitivity": ["secret", "third_party"], "notes": ""}}


def rec(cid, area="retrieval", channel="typed", tokens=10, injected=(), cost=None):
    return {"case_id": cid, "area": area, "subarea": "x", "level": "L2", "channel": channel, "difficulty": 3,
            "scoring": "context_recall", "expect": "answer", "passed": True, "score": 1.0, "verdict": None,
            "recall": 1.0, "leak": False, "leak_hits": [], "error": None, "tags": [],
            "gold": {"must_not_include_text": [], "must_not_include_facts": []}, "detail": {},
            "injected_facts": list(injected), "fact_precision": None, "own": None, "cost": cost or {},
            "context": {"text": "ctx", "item_ids": [], "tokens_est": tokens, "wall_ms": 1.0,
                        "latency_ms_reported": 0.0}}


def test_tokens_by_area_mean_and_p90():
    recs = [rec("a", tokens=10), rec("b", tokens=30), rec("c", area="scope", tokens=100)]
    t = report.summarize(recs, FACTS, {"adapter": "x"})["context"]["tokens_by_area"]
    assert t["retrieval"] == {"n": 2, "mean": 20.0, "p90": 28.0}
    assert t["scope"] == {"n": 1, "mean": 100.0, "p90": 100.0}
    assert "Injected tokens by area" in report.render_markdown(report.summarize(recs, FACTS, {"adapter": "x"}))


def test_sensitive_facts_sent_overall_and_on_remote():
    recs = [rec("a", injected=["f1", "f2", "f3"]), rec("b", injected=["f2"]),
            rec("c", channel="remote", injected=["f3"]), rec("d", channel="remote")]
    s = report.summarize(recs, FACTS, {"adapter": "x"})
    sens = s["context"]["sensitive"]
    assert sens["all"] == {"n": 4, "facts_mean": 0.75, "share": 0.5}
    assert sens["remote"] == {"n": 2, "facts_mean": 0.5, "share": 0.5}
    assert "Sensitive truth facts" in report.render_markdown(s)


def test_upkeep_is_system_cost_outside_probes_per_replayed_day():
    recs = [rec("a", cost={"model_calls": 1, "input_tokens": 100}), rec("b", cost={"embed_calls": 2})]
    total = {"model_calls": 21, "input_tokens": 1100, "embed_calls": 2}
    s = report.summarize(recs, FACTS, {"adapter": "x", "replay": {"maintained": 10}}, system_cost=total)
    up = s["cost"]["upkeep"]
    assert up["total"] == {"model_calls": 20, "input_tokens": 1000, "embed_calls": 0}
    assert up["days"] == 10 and up["days_source"] == "replay"
    assert up["per_day"] == {"model_calls": 2.0, "input_tokens": 100.0, "embed_calls": 0.0}
    assert "Upkeep" in report.render_markdown(s)


def test_upkeep_assumes_the_world_span_without_replay_stats_and_is_null_without_system_cost():
    recs = [rec("a")]
    up = report.summarize(recs, FACTS, {"adapter": "x"}, system_cost={"model_calls": 184})["cost"]["upkeep"]
    assert up["days"] == 184 and up["days_source"] == "assumed" and up["per_day"] == {"model_calls": 1.0}
    none = report.summarize(recs, FACTS, {"adapter": "x"})["cost"]["upkeep"]
    assert none["total"] is None and none["per_day"] is None
    assert "not reported" in report.render_markdown(report.summarize(recs, FACTS, {"adapter": "x"}))


def recall_rec(cid, recall, must, missing=(), leak=False):
    r = rec(cid)
    r.update(recall=recall, leak=leak, score=0.0 if leak else recall, leak_hits=["context: fact fx"] if leak else [])
    r["gold"]["must_include_facts"] = list(must)
    r["detail"] = {"missing_facts": list(missing)}
    return r


ORIGIN = {"u1": {"stated_by": "principal"}, "u2": {"stated_by": "assistant"}, "o1": {"stated_by": "p006"},
          "o2": {"stated_by": "u009"}}


def test_recall_without_leak_zeroes_a_case_that_leaked_and_keeps_recall_mean():
    recs = [recall_rec("a", 1.0, ["u1"]), recall_rec("b", 1.0, ["u2"], leak=True),
            recall_rec("c", 0.5, ["u1", "o1"], missing=["o1"]), rec("d")]
    recs[3]["recall"] = None  # not a recall case
    s = report.summarize(recs, ORIGIN, {"adapter": "x"})
    c = s["context"]
    assert c["recall_n"] == 3
    assert c["recall_mean"] == 2.5 / 3
    assert c["recall_without_leak_mean"] == 1.5 / 3
    assert "without leaking" not in report.render_markdown(s).lower()  # summary.json keeps it; the report does not


def test_wilson_interval_matches_known_values():
    lo, hi = report.wilson(16 / 23, 23)
    assert round(lo, 3) == 0.491 and round(hi, 3) == 0.844
    lo, hi = report.wilson(1.0, 10)
    assert hi == 1.0 and round(lo, 3) == 0.722
    assert report.wilson(None, 0) is None and report.wilson(0.5, 0) is None
    c = report.summarize([recall_rec("a", 1.0, ["u1"]), recall_rec("b", 0.0, ["u1"], missing=["u1"])], ORIGIN,
                         {"adapter": "x"})["context"]
    assert c["recall_ci95"][0] < 0.5 < c["recall_ci95"][1]
    assert c["recall_without_leak_ci95"] == c["recall_ci95"]


def test_recall_by_fact_origin_splits_needed_facts_by_who_stated_them():
    recs = [recall_rec("a", 1.0, ["u1", "u2"]), recall_rec("b", 0.5, ["u1", "o1"], missing=["o1"]),
            recall_rec("c", 0.5, ["o2", "u2"], missing=["u2"], leak=True)]
    s = report.summarize(recs, ORIGIN, {"adapter": "x"})
    by = s["context"]["recall_by_fact_origin"]
    assert {k: (v["found"], v["facts"]) for k, v in by.items()} == {"user_or_assistant": (3, 4), "others": (1, 2)}
    assert by["user_or_assistant"]["rate"] == 0.75 and by["others"]["rate"] == 0.5
    assert by["others"]["ci95"] == report.wilson(0.5, 2)
    md = report.render_markdown(s)
    assert "stated by" not in md  # summary.json keeps the split; the report prints no raw recall


def test_answered_right_is_the_share_of_cases_passed_and_leads_the_report():
    recs = [rec("a"), rec("b"), rec("c"), rec("d")]
    recs[1]["passed"] = False
    recs[2]["error"] = "boom"  # a harness error is not scored
    s = report.summarize(recs, FACTS, {"adapter": "x"})
    right = s["headline"]["answered_right"]
    assert right["rate"] == 2 / 3 and right["n"] == 3
    assert right["ci95"] == report.wilson(2 / 3, 3)
    md = report.render_markdown(s)
    assert md.index("Answered right") < md.index("Overall (mean of area pass rates)")
    assert "answered right 66.7%" in report.headline_text(s)


RECALL_LABELS = ("Gold-fact recall", "Needed facts found", "context recall", "token-matched recall",
                 "Recall found without leaking", "recall_mean", "Found without leaking", "without leaking",
                 "leak-adjusted", "mean score")


def test_a_report_prints_no_recall_label_or_figure():
    recs = [recall_rec("a", 1.0, ["u1"]), recall_rec("b", 1.0, ["u2"], leak=True),
            recall_rec("c", 0.5, ["u1", "o1"], missing=["o1"]), rec("d")]
    s = report.summarize(recs, ORIGIN, {"adapter": "x"})
    for md in (report.render_markdown(s), report.render_markdown(s, recs, ORIGIN), report.headline_text(s)):
        assert not [label for label in RECALL_LABELS if label.lower() in md.lower()]
        assert "83.3%" not in md and "0.8" not in md  # the plain recall mean, 2.5/3, as a percentage or a mean score
        assert "50.0%" not in md  # found without leaking, 1.5/3


def test_rebuild_from_a_summary_saved_before_answered_right_or_leak_adjusted_recall(tmp_path):
    recs = [recall_rec("a", 1.0, ["u1"]), recall_rec("b", 1.0, ["u2"], leak=True), rec("c")]
    recs[2]["recall"] = None
    s = report.summarize(recs, ORIGIN, {"adapter": "x"})
    del s["headline"]["answered_right"]
    for k in ("recall_n", "recall_ci95", "recall_without_leak_mean", "recall_without_leak_ci95"):
        del s["context"][k]
    dev, test = tmp_path / "dev", tmp_path / "test"
    for d in (dev, test):
        d.mkdir()
        (d / "summary.json").write_text(json.dumps(s))
    (dev / "cases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    report.rebuild(dev, ORIGIN)
    report.rebuild(test, ORIGIN)
    md = (dev / "report.md").read_text()
    assert "Answered right" in md and "**100.0%**" in md and "(n=3)" in md
    for text in (md, (test / "report.md").read_text()):
        assert "without leaking" not in text.lower()
        assert "recall" not in text.lower().replace("| context_recall |", "")  # the scoring type's pass rate stays
    assert json.loads((dev / "summary.json").read_text()) == s  # the saved summary is not rewritten
