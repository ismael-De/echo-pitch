"""Deterministic match analytics. Every public function takes plain event dicts and returns JSON-serialisable data,
so they can be exposed directly as agent tools later."""
from .stats import (match_clock, possession, pass_difficulty, pass_summary, xg_timeline, pressure_index,
                    momentum, key_moments, control_vs_chaos, pressure_shifts, rhythm, match_state)

__all__ = ["match_clock", "possession", "pass_difficulty", "pass_summary", "xg_timeline", "pressure_index",
           "momentum", "key_moments", "control_vs_chaos", "pressure_shifts", "rhythm", "match_state"]
