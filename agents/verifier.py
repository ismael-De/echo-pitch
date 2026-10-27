"""Verifier (Guard) agent: deterministic fact check of every commentary line before it is shown.

No LLM is involved. Every number in a line must match a value in the facts the writer was given
(with display rounding), and every player name must belong to a player in those facts. A known
roster player who is not in the facts, or an unknown capitalised name, is rejected. The verifier
returns the evidence for each claim (which fact supports it) so the UI can footnote the line.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")
_NUM = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")
_CAP2 = re.compile(r"\b([A-Z][a-z'\-]+(?:\s+[A-Z][a-z'\-]+)+)\b")
_DEC_COMMA = re.compile(r"(?<!\d)(\d{1,3}),(\d{1,3})(?!\d)")
_ALWAYS = {100.0}  # scales such as "65.6/100" or "58 times in 100"


@dataclass
class Verdict:
    ok: bool
    evidence: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "evidence": self.evidence, "problems": self.problems}


def _walk(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def _numbers_of(path: str, v: Any) -> list[tuple[float, str, str]]:
    """(value, source_path, how) pairs a fact supports, including display forms."""
    out: list[tuple[float, str, str]] = []
    if isinstance(v, bool) or v is None:
        return out
    if isinstance(v, (int, float)):
        x = float(v)
        out += [(x, path, "exact"), (float(round(x)), path, "rounded"), (round(x, 1), path, "rounded"),
                (round(x, 2), path, "rounded")]
        if 0 < x < 1.5 and not float(x).is_integer():
            out.append((float(round(x * 100)), path, "as %"))
        if path.split(".")[-1] == "minute":
            out.append((x + 1, path, "display minute"))
        return out
    if isinstance(v, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", v.strip()):
        return _numbers_of(path, float(v))
    if isinstance(v, str):
        for m in _NUM.findall(v.translate(_AR_DIGITS)):
            out.append((float(m), path, "in text"))
    return out


_PAIR = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)%?\s?[-–—]\s?(\d+(?:\.\d+)?)(?![\d.]*\s?[-–—]\s?\d)")


class Verifier:
    """Holds the roster for one match; `check(text, facts)` returns a Verdict."""
    name = "verifier"

    def __init__(self, meta: dict):
        self.players = sorted({p["name"] for s in ("home", "away") for p in meta[s]["lineup"]}, key=len, reverse=True)
        self.teams = [meta[s]["name"] for s in ("home", "away")]
        self.codes = [meta[s]["code"] for s in ("home", "away") if meta[s].get("code")]
        self.known_caps = set(self.players) | set(self.teams) | {meta.get("venue", "")}

    @staticmethod
    def _pairs(flat: list[tuple[str, Any]]) -> list[tuple[float, float, str]]:
        """Two-sided facts (home/away dicts and 'a-b' strings) that a written 'a-b' may refer to."""
        out: list[tuple[float, float, str]] = []
        groups: dict[str, list[tuple[str, Any]]] = {}
        for p, v in flat:
            parent = p.rsplit(".", 1)[0] if "." in p else ""
            groups.setdefault(parent, []).append((p, v))
            if isinstance(v, str):
                for m in _PAIR.finditer(v.translate(_AR_DIGITS)):
                    out.append((float(m.group(1)), float(m.group(2)), p))
        for parent, items in groups.items():
            nums = [(p, float(v)) for p, v in items if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if len(nums) == 2:
                (_, a), (_, b) = nums
                for f in (lambda x: x, round, lambda x: round(x, 1), lambda x: round(x, 2)):
                    out.append((float(f(a)), float(f(b)), parent))
        # a team pair split across dicts (e.g. xg_h / xg_a)
        keys = {p: v for p, v in flat if isinstance(v, (int, float)) and not isinstance(v, bool)}
        for p, v in keys.items():
            if p.endswith("_h") and p[:-2] + "_a" in keys:
                a, b = float(v), float(keys[p[:-2] + "_a"])
                out += [(a, b, p[:-2]), (float(round(a)), float(round(b)), p[:-2])]
        return out

    def check(self, text: str, facts: dict) -> Verdict:
        flat = list(_walk(facts))
        strings = " | ".join(str(v) for _, v in flat if isinstance(v, str))
        nums: list[tuple[float, str, str]] = [(x, "scale", "constant") for x in _ALWAYS]
        for p, v in flat:
            nums += _numbers_of(p, v)
        ev, bad = [], []
        t = _DEC_COMMA.sub(r"\1.\2", text.translate(_AR_DIGITS))  # "0,54" (fr/es/pt) -> "0.54"
        pairs = self._pairs(flat)
        for m in _PAIR.finditer(t):
            a, b = float(m.group(1)), float(m.group(2))
            before, after = t[:m.start()].rstrip(), t[m.end():].lstrip()
            is_score = "." not in m.group(0) and any(before.endswith(c) or after.startswith(c)
                                                      for c in self.codes + self.teams)  # "SHF 1-0 BRT"
            cand = [p for p in pairs if "score" in p[2]] if is_score and any("score" in p[2] for p in pairs) else pairs
            hit = next((p for p in cand if (abs(p[0] - a) < 0.006 and abs(p[1] - b) < 0.006)
                        or (abs(p[0] - b) < 0.006 and abs(p[1] - a) < 0.006)), None)
            if hit:
                ev.append({"claim": m.group(0).strip(), "fact": hit[2], "how": "pair"})
            else:
                bad.append(f"pair {m.group(0).strip()} does not match any score or stat pair")
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
        for m in _NUM.finditer(t):
            x = float(m.group())
            hit = next((n for n in nums if abs(n[0] - x) < 0.006), None)
            if hit:
                if hit[1] != "scale":
                    ev.append({"claim": m.group(), "fact": hit[1], "how": hit[2]})
            else:
                bad.append(f"number {m.group()} is not in the match facts")
        # names: roster players mentioned must be in the facts
        rest = t
        for name in self.players:
            if name in rest:
                rest = rest.replace(name, " ")
                if name in strings:
                    ev.append({"claim": name, "fact": "player", "how": "in facts"})
                else:
                    bad.append(f"player {name} is not part of this event")
        for name in self.teams:
            if name in rest:
                rest = rest.replace(name, " ")
                ev.append({"claim": name, "fact": "team", "how": "in match"})
        allowed_tokens = {w for s in re.findall(r"[A-Za-z'\-]+", strings) for w in [s]}
        surnames = {n.split()[-1]: n for n in self.players}
        for w in re.findall(r"\b[A-Z][a-z'\-]+\b", rest):
            if w in surnames and w not in allowed_tokens:
                bad.append(f"player {surnames[w]} is not part of this event")
        for cand in _CAP2.findall(rest):
            words = cand.split()
            if all(w in allowed_tokens for w in words) or cand in self.known_caps:
                continue
            if any(w in surnames or len(w) > 2 for w in words) and words[0] not in _SENT_START:
                bad.append(f"unknown name {cand}")
        return Verdict(ok=not bad, evidence=ev, problems=bad)


_SENT_START = {"What", "And", "But", "The", "That", "This", "Off", "On", "Stats", "Kick", "Half", "Full", "Save",
               "Player", "Goals", "Ball", "Pass", "Big", "Huge", "Brilliant", "Oh", "Here", "Now", "Late", "Early",
               "Echo", "Pitch", "Premier", "League", "Expected", "Goal", "Goals", "Tremendous", "Superb", "Great"}
