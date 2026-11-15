"""harness/adapters/dawnmere.py: model routing without the engine; end to end on the mini fixture (slow: it downloads
the released engine and its models, then runs them with a fake model)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from harness import data, llm
from harness.adapter import AdapterError
from harness.adapters import dawnmere
from harness.data import session_view
from harness.prompts import _ISOLATION

FIX = Path(__file__).parent / "fixtures" / "mini"


class FakeLLM:
    def __init__(self, fail=None):
        self.calls, self.fail, self.stats = [], fail, {"calls": 0}

    def complete(self, model, system, prompt, schema=None, nonce=""):
        self.calls.append((model, system, prompt, schema))
        if self.fail:
            raise llm.LLMError(self.fail)
        return {"ok": True}


def test_engine_calls_get_the_benchmark_model_and_the_isolation_sentence(monkeypatch):
    monkeypatch.delenv("DAWNMERE_BENCH_MODELS", raising=False)
    a = dawnmere.Dawnmere()
    a.llm = FakeLLM()
    out = a._model({"model": "haiku", "system": "You file entries.", "prompt": "p", "schema": {"type": "object"},
                    "job": "classify"})
    assert out == {"ok": True, "output": {"ok": True}}
    model, system, prompt, schema = a.llm.calls[0]
    assert model == llm.DEFAULT_ANSWERER and system == "You file entries.\n\n" + _ISOLATION and prompt == "p"
    assert a.jobs == {"classify": 1} and a.name == "dawnmere"


def test_product_models_follow_the_engine_settings(monkeypatch):
    monkeypatch.setenv("DAWNMERE_BENCH_MODELS", "product")
    a = dawnmere.Dawnmere()
    a.llm = FakeLLM()
    a._model({"model": "haiku", "system": "s", "prompt": "p"})
    assert a.llm.calls[0][0] == "claude-haiku-5-5" and a.name == "dawnmere-product-models"
    monkeypatch.setenv("DAWNMERE_BENCH_MODELS", "cheap")
    with pytest.raises(AdapterError):
        dawnmere.Dawnmere()


def test_a_failed_call_goes_back_to_the_engine_but_a_usage_cap_stops_the_run(monkeypatch):
    monkeypatch.delenv("DAWNMERE_BENCH_MODELS", raising=False)
    a = dawnmere.Dawnmere()
    a.llm = FakeLLM(fail="no structured_output in the response")
    assert a._model({"model": "haiku", "system": "s", "prompt": "p"})["ok"] is False
    a.llm = FakeLLM(fail="error result: usage_limit_reached")
    with pytest.raises(AdapterError):
        a._model({"model": "haiku", "system": "s", "prompt": "p"})


def test_a_local_wheel_must_be_an_engine_wheel(monkeypatch, tmp_path):
    monkeypatch.setenv("DAWNMERE_WHEEL", str(tmp_path / "something-0.1.0-py3-none-any.whl"))
    with pytest.raises(AdapterError):
        dawnmere.install()


def fill(schema):
    """The smallest value a JSON schema accepts: what a model that finds nothing would answer."""
    t = schema.get("type")
    t = next((x for x in t if x != "null"), "null") if isinstance(t, list) else t
    if "enum" in schema:
        return schema["enum"][0]
    if t == "object":
        return {k: fill(v) for k, v in (schema.get("properties") or {}).items() if k in (schema.get("required") or [])}
    return {"array": [], "string": "", "integer": 0, "number": 0, "boolean": False}.get(t)


class SchemaLLM(FakeLLM):
    def complete(self, model, system, prompt, schema=None, nonce=""):
        self.calls.append((model, system, prompt, schema))
        return fill(schema or {})


@pytest.mark.slow
def test_end_to_end_on_the_mini_fixture(tmp_path):
    ds = data.load(FIX)
    a = dawnmere.Dawnmere()
    a.llm = SchemaLLM()
    store = tmp_path / "work" / "store"
    store.mkdir(parents=True)
    a.reset(store)
    try:
        assert a.context("what do you know about me?", "typed", "probe-empty").item_ids == []
        for s in ds.sessions:
            a.set_clock(data.ts(s["end_ts"]).timestamp())
            a.ingest(session_view(s, ds.device_names))
        a.maintain()
        # s0004 is an inbound email with no user turn: the user asks for it in words that carry no facts, and the
        # email itself stays a tool result
        lines = [json.loads(x) for x in (store / "transcripts" / "s0004.jsonl").read_text().splitlines()]
        users = [e["message"]["content"] for e in lines if e["type"] == "user"]
        assert isinstance(users[0], str) and users[0].startswith("read the new message from ")
        assert users[1][0]["type"] == "tool_result"
        r = a.context("what time is my dentist appointment?", "typed", "probe-1")
        assert isinstance(r.text, str) and all(i.startswith(("m", "c")) for i in r.item_ids)
        assert a.context("what time is my dentist appointment?", "remote", "probe-2").tokens >= 0
        a.close()
        shutil.copytree(store, tmp_path / "snap")
        a.reopen()
        assert a.guard() == {"refused": []}
        assert a.llm.calls and all(m == llm.DEFAULT_ANSWERER for m, *_ in a.llm.calls)
        assert json.loads((store.parent / "dawnmere-engine.json").read_text())["engine_version"]
    finally:
        a._stop()


def test_seed_saves_the_users_facts_and_outside_ones(tmp_path):
    # L1 seeding named its origin hao_typed, which no engine since 0.1.4 accepts.
    a = dawnmere.Dawnmere()
    a.llm = SchemaLLM()
    store = tmp_path / "work" / "store"
    store.mkdir(parents=True)
    a.reset(store)
    try:
        facts = [{"fact_id": "f1", "text": "My dentist appointment is at 3pm on Friday.", "stated_by": "principal"},
                 {"fact_id": "f2", "text": "The office closes at 6pm.", "stated_by": "contact"}]
        a.seed(facts)
        assert a.context("what time is my dentist appointment?", "typed", "probe-1").item_ids
    finally:
        a._stop()


def test_sessions_and_probes_reach_the_engine_as_claude_code(tmp_path):
    # Since engine 0.1.6 a hook call is Claude Code's (desk) only for a transcript at <projects>/<folder>/<id>.jsonl;
    # the bridge's probe.jsonl and store/transcripts made every call an unknown client that sees work only.
    a = dawnmere.Dawnmere()
    a.llm = SchemaLLM()
    store = tmp_path / "work" / "store"
    store.mkdir(parents=True)
    a.reset(store)
    a._stop()
    check = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("bridge", sys.argv[1])
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
out = {}
for sid, event in (("s0001", "SessionStart"), ("s0001", "UserPromptSubmit"), ("probe-a-capture-0001", "SessionStart"),
                   ("probe-a-capture-0001", "UserPromptSubmit")):
    data = {"session_id": sid, "cwd": b.HOME, "transcript_path": str(b.transcript(sid)), "hook_event_name": event}
    out[f"{sid} {event}"] = list(b.mem.hook_client(data)[0])
sys.__stdout__.write(json.dumps(out))
"""
    r = subprocess.run([a.info["python"], "-I", "-B", "-c", check, str(dawnmere.BRIDGE)], env=a._env(store.resolve()),
                       cwd=str(store), capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    got = json.loads(r.stdout)
    assert len(got) == 4 and all(v == ["desk", True] for v in got.values()), got


def test_channel_aware_modes_are_opt_in_and_named(monkeypatch):
    for access in ("channel-aware", "channel-aware-strict", "channel-aware-workonly"):
        monkeypatch.setenv("DAWNMERE_BENCH_ACCESS", access)
        assert dawnmere.Dawnmere().name == f"dawnmere-{access}"
    monkeypatch.delenv("DAWNMERE_BENCH_ACCESS")
    assert dawnmere.Dawnmere().name == "dawnmere"


def bridge_script(tmp_path, script):
    """Run script in the engine's environment with the bridge loaded as b (its store made by the adapter); its JSON."""
    a = dawnmere.Dawnmere()
    a.llm = SchemaLLM()
    store = tmp_path / "work" / "store"
    store.mkdir(parents=True)
    a.reset(store)
    a._stop()
    head = ("import importlib.util, json, sys\n"
            "spec = importlib.util.spec_from_file_location('bridge', sys.argv[1])\n"
            "b = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(b)\n")
    r = subprocess.run([a.info["python"], "-I", "-B", "-c", head + script, str(dawnmere.BRIDGE)],
                       env=a._env(store.resolve()), cwd=str(store), capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


PROBE_CLIENTS = """
m = b.mem
out = {"work_hide": sorted(m.WORK_HIDE), "profile_telegram": sorted(m.RESTRICTED.get("telegram", ()))}
for channel in ("typed", "voice", "web", "remote"):
    for event in ("SessionStart", "UserPromptSubmit"):
        data = {**b.probe_payload(channel, "probe-a-capture-0001"), "hook_event_name": event}
        who, sent = m.hook_client(data)
        out[f"{channel} {event}"] = [list(who), sent, sorted(m.client_hide(*who))]
sys.__stdout__.write(json.dumps(out))
"""


@pytest.mark.parametrize("access", ["product", "channel-aware", "channel-aware-strict", "channel-aware-workonly"])
def test_only_a_workonly_remote_probe_comes_from_another_app(tmp_path, monkeypatch, access):
    # channel-aware-workonly: an app that is not Claude Code and names no client, which engine 0.1.10's hook_client
    # makes the unknown client with the work-only view. Every other probe, in every mode, is Claude Code's at the desk,
    # which sees everything (channel-aware and -strict filter the remote context afterwards: _phone_view).
    monkeypatch.setenv("DAWNMERE_BENCH_ACCESS", access)
    got = bridge_script(tmp_path, PROBE_CLIENTS)
    work_hide, telegram = got.pop("work_hide"), got.pop("profile_telegram")
    assert set(work_hide) == {"chats", "health-money", "people", "personal"}
    # Why channel-aware filters in the harness: the generic profile Dawnmere ships has no phone scope of its own
    # (profiles/generic.py: restricted={}, so the engine's telegram scope hides nothing). If an engine adds one, look.
    assert telegram == []
    for key, (who, sent, hide) in got.items():
        if access == "channel-aware-workonly" and key.startswith("remote "):
            assert who == ["unknown", False] and sent == {"name": "unknown", "key": None} and hide == work_hide, key
        else:
            assert who == ["desk", True] and sent is None and hide == [], key


PHONE_VIEW = """
from lflabs_memory import claimstore
m, br = b.mem, b.Bridge()
db = br.db
claimstore.migrate(db)
mid = lambda text, **kw: m.remember(db, text, "reference", origin="outside", via="desk", **kw)[0]
ids = {"plain": mid("The office wiki lives at wiki.example.com."),
       "health": mid("Her doctor prescribed 20 mg of sertraline for anxiety."),
       "meeting": mid("In a meeting on 2026-05-02 the team moved the launch to June 9.", source="meeting:bench-1#1"),
       "unfiled": mid("The bike shop on Elm Street opens at nine.")}
with db:
    db.execute("update memories set section = null, section2 = null where id = ?", (ids["unfiled"],))
cl = lambda text, ch: "c" + str(claimstore.add(m, db, text, "outside", channel=ch)[0])
ids.update({"claim_talk": cl("Leo said the new bakery on Pine Street opens on Monday.", "conversation"),
            "claim_meeting": cl("In the planning meeting Ana said the budget review moves to Thursday.", "meeting"),
            "claim_read": cl("A message Gerald sent says the boiler will be serviced on May 20.", "read"),
            "claim_money": cl("Leo said his salary went up to 90,000 euros a year.", "conversation")})
text = "Recalled from Dawnmere (long-term memory):\\n" + "\\n".join(
    f"- #{v} [tag] line {k}" for k, v in ids.items())
shown = lambda t: sorted(k for k, v in ids.items() if f"#{v} " in t)
out = {"loose": shown(br._phone_view(text)), "strict": shown(br._phone_view(text, strict=True)),
       "only_hidden": br._phone_view("Recalled from Dawnmere:\\n- #" + ids["claim_read"] + " x")}
sys.__stdout__.write(json.dumps(out))
"""


def test_the_phone_view_leaves_out_meetings_reads_and_unfiled_and_strict_health_and_money(tmp_path):
    got = bridge_script(tmp_path, PHONE_VIEW)
    assert got["loose"] == ["claim_money", "claim_talk", "health", "plain"]
    assert got["strict"] == ["claim_talk", "plain"]
    assert got["only_hidden"] == ""  # nothing left: no context at all, as _telegram_view


SEED = [{"fact_id": "f1", "text": "My dentist appointment is at 3pm on Friday.", "stated_by": "principal"},
        {"fact_id": "f2", "text": "The office wiki lives at wiki.example.com.", "stated_by": "contact"}]
ASK = "what time is my dentist appointment and where is the office wiki?"


@pytest.mark.parametrize("access,dentist_on_remote", [("product", True), ("channel-aware", True),
                                                       ("channel-aware-strict", False),
                                                       ("channel-aware-workonly", False)])
def test_what_a_remote_probe_sees_in_each_mode(tmp_path, monkeypatch, access, dentist_on_remote):
    # The engine's own filing with no model: the user's fact is personal, a pointer from outside is reference. A
    # dentist appointment is health to the engine's local sensitivity labels (not its word list).
    monkeypatch.setenv("DAWNMERE_BENCH_ACCESS", access)
    a = dawnmere.Dawnmere()
    a.llm = SchemaLLM()
    store = tmp_path / "work" / "store"
    store.mkdir(parents=True)
    a.reset(store)
    try:
        a.seed(SEED)
        assert "dentist" in a.context(ASK, "typed", "probe-1").text
        remote = a.context(ASK, "remote", "probe-2").text
        assert ("dentist" in remote) is dentist_on_remote
        if access == "channel-aware-workonly":
            assert "wiki.example.com" in remote  # work only, not nothing
        assert "dentist" in a.context(ASK, "typed", "probe-3").text
        assert a.guard() == {"refused": []}
    finally:
        a._stop()


class EqualAccessLLM(SchemaLLM):
    """The smallest answers, except: the brain step remembers one fact, the text intake saves one fact per contact."""

    def complete(self, model, system, prompt, schema=None, nonce=""):
        self.calls.append((model, system, prompt, schema))
        props = (schema or {}).get("properties") or {}
        if "calls" in props:
            return {"calls": [{"turn": 1, "tool": "remember", "kind": "user", "project": None,
                               "content": "Benchmark brain note: the user likes oat milk cortados."}]}
        if "facts" in props and "title" not in props:
            names = sorted(set(re.findall(r"saved contact: ([^:\]]+):", prompt)))
            return {"facts": [{"name": n, "fact": f"{n} is coming to dinner on 2026-03-20."} for n in names]}
        return fill(schema or {})


def test_equal_access_mode_is_opt_in_and_named(monkeypatch):
    monkeypatch.setenv("DAWNMERE_BENCH_ACCESS", "equal")
    assert dawnmere.Dawnmere().name == "dawnmere-equal-access"
    monkeypatch.setenv("DAWNMERE_BENCH_ACCESS", "everything")
    with pytest.raises(AdapterError):
        dawnmere.Dawnmere()


@pytest.mark.slow
def test_equal_access_end_to_end_on_the_mini_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("DAWNMERE_BENCH_ACCESS", "equal")
    ds = data.load(FIX)
    a = dawnmere.Dawnmere()
    a.llm = EqualAccessLLM()
    store = tmp_path / "work" / "store"
    store.mkdir(parents=True)
    a.reset(store)
    try:
        for s in ds.sessions:
            a.set_clock(data.ts(s["end_ts"]).timestamp())
            a.ingest(session_view(s, ds.device_names))
        a.maintain()
        assert a.jobs.get("brain", 0) >= 1                       # the assistant's own memory calls were asked for
        r = a.context("do I like cortados?", "typed", "probe-1")
        assert "oat milk cortado" in r.text                     # and its remember reached the engine
        assert a.guard() == {"refused": []}
        assert json.loads((store.parent / "dawnmere-engine.json").read_text())["access"] == "equal"
    finally:
        a._stop()
