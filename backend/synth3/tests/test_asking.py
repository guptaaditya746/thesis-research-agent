"""synth3.asking: one checked call, one repair, a raising call as a problem, and `fresh` past the cache.
Every model is a fake; none is a live call."""
from pathlib import Path

from modelcall import CallSettings, JsonlCache
from synth2.recipe import Strict
from synth3.asking import MAX_REPAIRS, ask_checked, repair_input
from synth3.tests.fakes import boom, failing, scripted

PROMPT = Path(__file__).parent / "fixtures" / "prompts" / "word-v1.txt"
SETTINGS = CallSettings()


class Reply(Strict):
    word: str


def check(r: Reply) -> list[str]:
    return [] if r.word == "ok" else ["word is not ok"]


def test_a_good_reply_takes_one_call(tmp_path):
    model = scripted(Reply(word="ok"))
    out = ask_checked(PROMPT, Reply, "x", check, model, JsonlCache(tmp_path / "c"), SETTINGS)
    assert out["reply"] == Reply(word="ok") and out["calls"] == 1 and out["problems"] == []
    assert out["served_models"] == ["fake"] and len(out["prompt_sha256"]) == 64


def test_a_failed_check_gets_one_repair_with_the_input_and_the_problem(tmp_path):
    model = scripted(Reply(word="no"), Reply(word="ok"))
    out = ask_checked(PROMPT, Reply, "the task input", check, model, JsonlCache(tmp_path / "c"), SETTINGS)
    assert out["reply"].word == "ok" and out["calls"] == 2
    assert "the task input" in model.prompts[1] and "word is not ok" in model.prompts[1]


def test_two_failed_checks_give_no_reply(tmp_path):
    model = scripted(Reply(word="no"), Reply(word="still no"))
    out = ask_checked(PROMPT, Reply, "x", check, model, JsonlCache(tmp_path / "c"), SETTINGS)
    assert MAX_REPAIRS == 1
    assert out["reply"] is None and out["calls"] == 2 and out["problems"] == ["word is not ok"]


def test_a_raising_call_is_a_problem_not_a_crash(tmp_path):
    out = ask_checked(PROMPT, Reply, "x", check, failing(), JsonlCache(tmp_path / "c"), SETTINGS)
    assert out["reply"] is None and out["problems"][0].startswith("model call failed")


def test_a_raising_repair_keeps_the_first_problems(tmp_path):
    first = scripted(Reply(word="no"))
    c = JsonlCache(tmp_path / "c")
    ask_checked(PROMPT, Reply, "x", lambda r: [], first, c, SETTINGS)   # caches the first reply
    model = boom()
    out = ask_checked(PROMPT, Reply, "x", check, model, c, SETTINGS)
    assert model.calls == 1 and out["calls"] == 2 and out["reply"] is None
    assert out["problems"][0].startswith("model call failed") and "word is not ok" in out["problems"]


def test_fresh_skips_the_cache(tmp_path):
    c = JsonlCache(tmp_path / "c"); first = scripted(Reply(word="ok")); again = scripted(Reply(word="ok"))
    ask_checked(PROMPT, Reply, "x", check, first, c, SETTINGS)
    ask_checked(PROMPT, Reply, "x", check, again, c, SETTINGS)
    assert len(again.prompts) == 0
    ask_checked(PROMPT, Reply, "x", check, again, c, SETTINGS, fresh="t1")
    assert len(again.prompts) == 1


def test_repair_input_holds_the_input_the_reply_and_the_problems():
    text = repair_input("the task input", Reply(word="no"), ["a", "b"])
    assert text.startswith("the task input") and '{"word":"no"}' in text
    assert text.endswith("Fix only these problems:\na\nb")
