"""Possession-chain simulator producing football-realistic synthetic event data.

Coordinates: metres on a 105 x 68 pitch, absolute frame. The HOME team always
attacks towards x=105 and the AWAY team towards x=0 (no half-time switch, to
keep downstream analytics simple). Times are match clock; second-half events
start at minute 45 and stoppage time continues past 45/90.
"""
from __future__ import annotations

import math
import random
from typing import Any

PITCH_L, PITCH_W = 105.0, 68.0
GOAL_W = 7.32
EVENT_TYPES = {"pass", "shot", "tackle", "carry", "pressure", "possession_change", "foul", "goal", "save"}

CLUBS = {
    "AVR": {"name": "Avonmere Rovers", "short": "AVR", "city": "Avonmere", "venue": "Harrowgate Park", "strength": 1.10},
    "CLW": {"name": "Coldwater Athletic", "short": "CLW", "city": "Coldwater", "venue": "The Mill Ground", "strength": 1.00},
    "SHF": {"name": "Saltmarsh FC", "short": "SHF", "city": "Saltmarsh", "venue": "Estuary Stadium", "strength": 0.95},
    "BRT": {"name": "Brackenridge Town", "short": "BRT", "city": "Brackenridge", "venue": "Fernhill Road", "strength": 1.05},
    "KNG": {"name": "Kingsfold United", "short": "KNG", "city": "Kingsfold", "venue": "Lantern Lane", "strength": 0.98},
    "WYE": {"name": "Wyecliffe City", "short": "WYE", "city": "Wyecliffe", "venue": "Cliffside Arena", "strength": 1.02},
}
FIXTURES = [("AVR", "CLW"), ("SHF", "BRT"), ("KNG", "WYE")]

FIRST = ["Ari", "Bram", "Caio", "Dario", "Emil", "Farid", "Goran", "Hugo", "Idris", "Jonas", "Kofi", "Luca",
         "Mateo", "Nils", "Omar", "Pavel", "Quinn", "Rafa", "Sami", "Tomas", "Umar", "Viktor", "Wes", "Yusuf", "Zane"]
LAST = ["Ashby", "Brennick", "Calloway", "Dunmore", "Eldridge", "Fenwick", "Garrow", "Holloway", "Iversen",
        "Jessop", "Kettering", "Lindqvist", "Marlow", "Norcross", "Okafor", "Pellham", "Quarry", "Rendell",
        "Stroud", "Thackeray", "Underhill", "Varga", "Whitlock", "Yardley", "Zeller"]

# 4-3-3: (position, shirt, base x, base y) in the attacking-team frame (attacking to x=105)
FORMATION = [("GK", 1, 5, 34), ("RB", 2, 30, 8), ("CB", 5, 22, 26), ("CB", 4, 22, 42), ("LB", 3, 30, 60),
             ("CM", 6, 42, 34), ("CM", 8, 52, 22), ("CM", 10, 55, 46), ("RW", 7, 75, 10), ("ST", 9, 82, 34),
             ("LW", 11, 75, 58)]
# relative weights for who is on the ball, by zone (defensive / middle / attacking third)
ZONE_WEIGHTS = {"GK": (6, 0.3, 0), "RB": (4, 3, 1.5), "CB": (6, 2, 0.3), "LB": (4, 3, 1.5), "CM": (3, 5, 2.5),
                "RW": (0.5, 3, 4), "ST": (0.3, 2, 5), "LW": (0.5, 3, 4)}


def xg_model(x: float, y: float) -> float:
    """Expected-goals from shot location (attacking frame, goal at x=105, y=34).

    Logistic on distance and the angle subtended by the goal mouth.
    Penalty spot ~0.24, 6 yards central ~0.58, 20m ~0.06, 30m ~0.02.
    """
    dx, dy = PITCH_L - x, abs(y - PITCH_W / 2)
    dist = math.hypot(dx, dy)
    a = math.atan2(GOAL_W * dx, dx * dx + dy * dy - (GOAL_W / 2) ** 2)
    if a < 0:
        a += math.pi
    return round(1 / (1 + math.exp(-(-1.2 + 2.0 * a - 0.11 * dist))), 3)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _squad(rng: random.Random, code: str, names: set[str]) -> list[dict[str, Any]]:
    """Build an 11-player lineup; `names` is shared across both clubs so names are unique in a match."""
    players = []
    for pos, num, bx, by in FORMATION:
        while True:
            n = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if n not in names:
                names.add(n)
                break
        players.append({"player_id": f"{code}-{num:02d}", "name": n, "position": pos, "number": num,
                        "base_x": bx, "base_y": by})
    return players


class _Match:
    def __init__(self, seed: int, home: str, away: str, match_no: int):
        self.rng = random.Random(seed)
        self.match_id = f"EP-2026-{match_no:03d}"
        self.teams = {"home": dict(CLUBS[home]), "away": dict(CLUBS[away])}
        used: set[str] = set()
        self.squads = {s: _squad(self.rng, self.teams[s]["short"], used) for s in ("home", "away")}
        self.shots = {"home": 0, "away": 0}
        self.events: list[dict[str, Any]] = []
        self.score = {"home": 0, "away": 0}
        self.momentum = 0.0  # >0 favours home, random walk in [-1, 1]
        self.t = 0.0  # seconds within current half
        self.half = 1
        self.half_len = 45 * 60 + self.rng.randint(60, 180)
        # scripted dramatic moments: (half, second) -> kind
        self.scripts = [(2, (39 + self.rng.random() * 4) * 60, "late_big_chance"),
                        (1, (25 + self.rng.random() * 10) * 60, "wonder_save")]

    # ---------- helpers ----------
    def _clock(self):
        base = 0 if self.half == 1 else 45 * 60
        s = int(base + self.t)
        return s // 60, s % 60

    def _abs(self, side, x, y):
        return (x, y) if side == "home" else (PITCH_L - x, PITCH_W - y)

    def _pick(self, side, x, exclude=None):
        zone = 0 if x < 35 else (1 if x < 70 else 2)
        pl = [p for p in self.squads[side] if p is not exclude]
        w = [ZONE_WEIGHTS[p["position"]][zone] + 0.05 for p in pl]
        return self.rng.choices(pl, w)[0]

    def _emit(self, side, player, etype, x, y, ex=None, ey=None, outcome=None, speed=None, pressure=0.0, xg=None):
        m, s = self._clock()
        ax, ay = self._abs(side, x, y)
        if ex is not None:
            ex, ey = self._abs(side, ex, ey)
        self.events.append({
            "match_id": self.match_id, "event_id": f"{self.match_id}-{len(self.events) + 1:05d}",
            "period": self.half, "minute": m, "second": s, "team": side,
            "team_name": self.teams[side]["name"], "player_id": player["player_id"], "player_name": player["name"],
            "type": etype, "x": round(_clamp(ax, 0, PITCH_L), 1), "y": round(_clamp(ay, 0, PITCH_W), 1),
            "end_x": None if ex is None else round(_clamp(ex, 0, PITCH_L), 1),
            "end_y": None if ey is None else round(_clamp(ey, 0, PITCH_W), 1),
            "outcome": outcome, "speed_kmh": None if speed is None else round(speed, 1),
            "pressure_level": round(pressure, 2), "xg": xg,
        })

    def _tick(self, lo, hi):
        self.t += self.rng.uniform(lo, hi)

    def _other(self, side):
        return "away" if side == "home" else "home"

    # ---------- shot ----------
    def _shot(self, side, player, x, y, wonder_save=False):
        self.shots[side] += 1
        xg = xg_model(x, y)
        speed = self.rng.uniform(60, 125) if x < 88 else self.rng.uniform(45, 95)
        opp = self._other(side)
        gk = self.squads[opp][0]
        r = self.rng.random()
        if wonder_save:
            r = 1.0  # cannot score; keeper saves
        ty = PITCH_W / 2 + self.rng.uniform(-3.4, 3.4)
        if r < xg:
            self._emit(side, player, "shot", x, y, 105, ty, "goal", speed, self._pressure(), xg)
            self._tick(0, 1)
            self._emit(side, player, "goal", 105, ty, outcome="scored", xg=xg)
            self.score[side] += 1
            self.momentum += 0.35 if side == "home" else -0.35
            self._tick(40, 70)  # celebration + restart
            return "goal"
        roll = self.rng.random()
        if wonder_save or roll < 0.40:
            self._emit(side, player, "shot", x, y, 105, ty, "saved", speed, self._pressure(), xg)
            self._tick(0, 1)
            gx, gy = PITCH_L - 104, PITCH_W - ty
            self._emit(opp, gk, "save", gx, gy, outcome="wonder_save" if wonder_save else "caught", speed=speed)
        elif roll < 0.65:
            blk = self._pick(opp, PITCH_L - x)
            self._emit(side, player, "shot", x, y, x + 2, y, "blocked", speed, self._pressure(), xg)
            self._tick(0, 1)
            self._emit(opp, blk, "tackle", PITCH_L - x - 2, PITCH_W - y, outcome="block")
        else:
            self._emit(side, player, "shot", x, y, 105, PITCH_W / 2 + self.rng.choice([-1, 1]) * self.rng.uniform(4, 12),
                       "off_target", speed, self._pressure(), xg)
        self.momentum += (0.06 + xg * 0.3) * (1 if side == "home" else -1)
        self._tick(6, 20)
        return "no_goal"

    def _pressure(self):
        return min(1.0, max(0.0, self.rng.gauss(0.35, 0.22)))

    # ---------- possession ----------
    def _possession(self, side, x, y):
        """Simulate one possession; returns (next_side, x, y) in next side's frame."""
        sgn = 1 if side == "home" else -1
        strength = self.teams[side]["strength"] / self.teams[self._other(side)]["strength"]
        mom = self.momentum * sgn  # positive = this team on top
        player = self._pick(side, x)
        opp = self._other(side)
        while True:
            if self._half_over():
                return None
            # scripted moments
            for sc in list(self.scripts):
                h, when, kind = sc
                # Fire only once this team has the ball in the attacking half, so the
                # sequence starts from the real ball position (no teleport).
                if h == self.half and self.t >= when and x >= 60:
                    self.scripts.remove(sc)
                    st = self._pick(side, 95, exclude=player)
                    tx, ty = (88.0, 31.0) if kind == "late_big_chance" else (85.0, 28.0)
                    dur = max(2.0, math.hypot(tx - x, ty - y) / 7.0)  # ~25 km/h
                    self._emit(side, player, "carry", x, y, tx, ty, "success",
                               math.hypot(tx - x, ty - y) / dur * 3.6, 0.6)
                    self.t += dur
                    sx, sy = (97.5, 33.0) if kind == "late_big_chance" else (94.0, 30.0)
                    self._emit(side, player, "pass", tx, ty, sx, sy, "complete", self.rng.uniform(45, 60), 0.7)
                    self._tick(1, 2)
                    self._shot(side, st, sx, sy, wonder_save=(kind == "wonder_save"))
                    return opp, 6, 34
            press = self._pressure() * (1 + 0.6 * (x / 105))
            press = min(press, 1.0)
            # opponent pressure event
            if self.rng.random() < 0.13 + 0.1 * (x / 105):
                presser = self._pick(opp, PITCH_L - x, exclude=self.squads[opp][0])
                self._emit(opp, presser, "pressure", PITCH_L - x, PITCH_W - y, outcome="applied", pressure=press)
                self._tick(0, 1)
                if self.rng.random() < 0.32:  # pressure wins the ball
                    self._emit(opp, presser, "tackle", PITCH_L - x, PITCH_W - y, outcome="won", pressure=press)
                    self._tick(1, 2)
                    if self.rng.random() < 0.18:  # some tackles are fouls instead
                        self.events.pop()
                        self._emit(opp, presser, "foul", PITCH_L - x, PITCH_W - y, outcome="free_kick")
                        self._tick(20, 45)
                        continue
                    self._emit(opp, presser, "possession_change", PITCH_L - x, PITCH_W - y, outcome="tackle")
                    self._tick(1, 2)
                    return opp, PITCH_L - x, PITCH_W - y
            # shooting chance in final third
            shoot_p = 0.0
            if x > 80:
                shoot_p = (0.03 + 0.06 * max(0, (x - 85) / 20)) * (1 + 0.15 * mom) * strength ** 0.5
                # soft cap on shot imbalance: damp the shooting rate once a team leads by >6 shots
                lead = self.shots[side] - self.shots[opp]
                shoot_p /= 1 + 0.3 * max(0, lead - 6)
            if self.rng.random() < shoot_p:
                res = self._shot(side, player, x, y)
                return opp, 52.5 if res == "goal" else 6, 34
            # carry or pass
            if self.rng.random() < 0.22:
                dx = self.rng.uniform(3, 14) * (1 + 0.3 * mom)
                ex, ey = _clamp(x + dx, 1, 98), _clamp(y + self.rng.uniform(-7, 7), 1, 67)
                dur = self.rng.uniform(2, 6)
                spd = math.hypot(ex - x, ey - y) / dur * 3.6
                self._emit(side, player, "carry", x, y, ex, ey, "success", spd, press)
                self.t += dur
                x, y = ex, ey
                continue
            # pass
            fwd = 4 + 6 * (1 + mom * 0.25)
            dx = self.rng.gauss(fwd, 12)
            dist_cap = 55 if x < 40 else 35
            ex = _clamp(x + max(-20, min(dist_cap, dx)), 1, 99)
            ey = _clamp(y + self.rng.gauss(0, 14), 1, 67)
            d = math.hypot(ex - x, ey - y)
            p_ok = 0.94 - 0.0045 * d - 0.12 * press - 0.12 * max(0, (ex - 75) / 30) + 0.02 * mom + 0.03 * (strength - 1)
            spd = self.rng.uniform(35, 55) + d * 0.6
            receiver = self._pick(side, ex, exclude=player)
            if self.rng.random() < p_ok:
                self._emit(side, player, "pass", x, y, ex, ey, "complete", spd, press)
                self._tick(2.0, 4.0)
                player, x, y = receiver, ex, ey
            else:
                self._emit(side, player, "pass", x, y, ex, ey, "incomplete", spd, press)
                self._tick(1, 2.5)
                if ex > 103 or ey < 1.5 or ey > 66.5:  # out of play
                    self._tick(5, 15)
                interceptor = self._pick(opp, PITCH_L - ex)
                self._emit(opp, interceptor, "possession_change", PITCH_L - ex, PITCH_W - ey, outcome="interception")
                self._tick(0.5, 1.5)
                return opp, PITCH_L - ex, PITCH_W - ey

    def _half_over(self):
        return self.t >= self.half_len

    def run(self):
        for half in (1, 2):
            self.half, self.t = half, 0.0
            if half == 2:
                self.half_len = 45 * 60 + self.rng.randint(120, 330)
            side = "home" if half == 1 else "away"
            x, y = 52.5, 34.0
            while not self._half_over():
                # momentum random walk with mean reversion
                self.momentum = _clamp(self.momentum * 0.97 + self.rng.gauss(0, 0.08), -1, 1)
                r = self._possession(side, x, y)
                if r is None:
                    break
                side, x, y = r
        return self.events

    def meta(self):
        def team(s):
            t = self.teams[s]
            return {"code": t["short"], "name": t["name"], "city": t["city"], "formation": "4-3-3",
                    "lineup": [{k: p[k] for k in ("player_id", "name", "position", "number")} for p in self.squads[s]]}
        return {"match_id": self.match_id, "competition": "Echo Pitch Synthetic League (fictional)",
                "venue": self.teams["home"]["venue"], "kickoff": f"2026-10-{24 + int(self.match_id[-1])}T15:00:00Z",
                "pitch": {"length_m": PITCH_L, "width_m": PITCH_W,
                          "orientation": "home attacks towards x=105, away towards x=0, both halves"},
                "home": team("home"), "away": team("away"), "final_score": dict(self.score),
                "synthetic": True}


def generate_match(seed: int = 42, home: str = "AVR", away: str = "CLW", match_no: int = 1):
    """Return (metadata dict, list of event dicts) for one deterministic synthetic match."""
    m = _Match(seed, home, away, match_no)
    events = m.run()
    return m.meta(), events
