"""The eval script's planted-error machinery (offline, one line) behaves as documented in docs/EVAL.md."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("eval_verifier", ROOT / "scripts" / "eval_verifier.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def test_corruptions_are_caught_and_clean_passes():
    meta = json.loads((ROOT / "data" / "EP-2026-002_meta.json").read_text())
    V = E.VM.Verifier(meta)
    facts = {"clock": "49'", "score_line": "SHF 0-1 BRT", "shooter": "Tomas Thackeray", "shooter_team": "Brackenridge Town",
             "opponent": "Saltmarsh FC", "xg": "0.98", "distance_m": 2, "shot_speed_kmh": 78}
    text = "Tomas Thackeray scores from 2m (xG 0.98), shot speed 78 km/h. SHF 0-1 BRT"
    rec = {"text": text, "facts": facts, "ok": True, "verifier": V, "us": 1.0}
    kinds = dict(E.corruptions(rec))
    assert set(kinds) == {"wrong_score_pair", "wrong_number", "wrong_player", "invented_player"}
    res = E.score([rec])
    assert res["clean_pass"] == 1
    assert res["caught_excl_team_swap"] == [4, 4]
