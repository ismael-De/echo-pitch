"""Spanish / French / Portuguese: template coverage, offline runs and the language guard."""
import pytest

from agents import templates as T
from agents.orchestrator import Prefs
from agents.specialists import WrongLanguage, check_language
from tests.test_agents import match, of, run  # noqa: F401  (fixture re-export)

NEW = ("es", "fr", "pt", "ru")


def _keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        out |= _keys(v, f"{prefix}{k}.") if isinstance(v, dict) else {f"{prefix}{k}"}
    return out


@pytest.mark.parametrize("lang", NEW)
def test_templates_cover_every_english_key(lang):
    for table in (T.LINES, T.MOMENTS, T.RECAP, T.TYPE_NAMES, T.FAVOURITE):
        assert _keys(table[lang]) == _keys(table["en"]), (lang, table is T.LINES)
    assert len(T.ZONES[lang]) == 3 and lang in T.SAFE


@pytest.mark.parametrize("lang", NEW)
def test_offline_match_in_language(match, lang):
    meta, ev = match
    _, items = run(meta, ev, Prefs("fan", lang))
    texts = [c["text"] for c in of(items, "commentary")] + [of(items, "recap")[0]["text"]]
    assert texts and all(c["lang"] == lang for c in of(items, "moment_card"))
    for t in texts:
        check_language(t, lang)


@pytest.mark.parametrize("text,lang", [
    ("The keeper gets down well and the shot from Luca Jessop is saved.", "es"),
    ("El portero se estira y la saca con la mano.", "en"),
    ("Le gardien est battu et c'est le but pour Saltmarsh FC.", "pt"),
    ("هدف رائع من Luca Jessop", "fr"),
    ("Вратарь отбивает удар Luca Jessop!", "en"),
    ("Le gardien est battu et c'est le but pour Saltmarsh FC.", "ru"),
    ("هدف رائع من Luca Jessop", "ru"),
])
def test_language_guard_rejects_wrong_language(text, lang):
    with pytest.raises(WrongLanguage):
        check_language(text, lang)


@pytest.mark.parametrize("text,lang", [
    ("¡Qué parada de Luca Jessop! El portero salva a su equipo.", "es"),
    ("Quel arrêt de Luca Jessop ! Le gardien sauve les siens.", "fr"),
    ("Que defesa de Luca Jessop! O goleiro salva o time.", "pt"),
    ("Какой сейв, Luca Jessop! Вратарь спасает Saltmarsh FC.", "ru"),
])
def test_language_guard_accepts_right_language(text, lang):
    check_language(text, lang)


@pytest.mark.parametrize("lang", ("en", "ar") + NEW)
def test_percentages_are_whole_numbers(match, lang):
    import re
    meta, ev = match
    _, items = run(meta, ev, Prefs("analyst", lang))
    texts = [c["text"] for c in of(items, "commentary")] + [of(items, "recap")[0]["text"]]
    assert not any(re.search(r"\d+\.\d+ ?%", t) for t in texts)


@pytest.mark.parametrize("text", [
    "The keeper is beaten and it's a goal for Saltmarsh FC.",
    "Гол and the crowd goes wild for Saltmarsh FC",
])
def test_russian_guard_rejects_non_russian(text):
    with pytest.raises(WrongLanguage):
        check_language(text, "ru")
