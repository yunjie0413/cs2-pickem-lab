"""Model v1 -> BO1/BO3 win probabilities for the teams of an event.

Runs the rating engine over the whole match history with the tuned
parameters, finds each event team by its lineup, and applies the fitted
calibration: the blend of our rating gap and the VRS points gap, then a
scale per format (BO1s are more random than BO3s; see Step 6b).
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np

from .baseline import map_from_bo3
from .history import load_history
from .model_v1 import LN10_400, Engine, Params


def load_config(root: Path) -> tuple[Params, dict]:
    cfg = json.loads((root / "data/processed/model_v1.json").read_text(encoding="utf-8"))
    params = Params(**{k: (math.inf if v is None else v) for k, v in cfg["params"].items()})
    return params, cfg


def load_model(root: Path, before: date | None = None) -> tuple[Engine, dict]:
    """Engine with every past match processed (only matches before `before`, if given, for backtests)."""
    params, cfg = load_config(root)
    h = load_history(root, use_hltv=cfg.get("hltv_links", 0) > 0)
    eng = Engine(params, h.regions, h.players)
    eng.run([m for m in h.inputs if before is None or m.date < before])
    return eng, cfg


def team_state(eng: Engine, name: str, roster: list[str], on: date) -> dict:
    """Effective rating, volatility and match count of an event team on a date.

    If the event roster differs from the team's latest lineup (a new signing
    or a stand-in), the player-rating adjustment is applied as in the engine.
    """
    lineup = frozenset(p.lower() for p in roster)
    tid, _ = eng.find(name, lineup)
    mu = eng.mean()
    if tid is None:
        return {"rating": mu, "vol": 0.0, "n": 0, "found": False}
    t = eng.teams[tid]
    rating = t.rating
    if t.last is not None and math.isfinite(eng.p.decay_days):
        rating = mu + (rating - mu) * math.exp(-max((on - t.last).days, 0) / eng.p.decay_days)
    roster_adj = eng.p.roster_skill * eng.skill_change(tid, lineup, name, on)
    region = eng.region_of(t)
    offset = eng.region_offset[region] if region else 0.0
    return {"rating": rating + roster_adj + offset, "vol": t.vol, "n": t.n, "played": t.played, "found": True,
            "matched_as": t.name, "last_match": t.last, "roster_adj": roster_adj,
            "joined": sorted(lineup - t.lineup) if t.lineup else [],
            "left": sorted(t.lineup - lineup) if t.lineup else []}


def event_matrices(eng: Engine, cfg: dict, teams: list[dict], on: date, bo3_scale: float = 1.0,
                   bo1_scale: float | None = None) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """(p_bo1, p_bo3, team states). teams: event-file entries in seed order.

    BO3: sigmoid(bo3_scale x blend logit), the blend (own rating gap + VRS
    points gap) as fitted on past matches of all formats. BO1: by default
    from the BO3 probability, assuming independent maps (Step 6b found this
    fits past BO1s as well as BO1s' own scale does); or sigmoid(bo1_scale x
    blend) if bo1_scale is given.
    """
    logit, states = event_logits(eng, cfg, teams, on)
    n = len(teams)
    p1, p3 = np.full((n, n), 0.5), np.full((n, n), 0.5)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            p3[i, j] = 1 / (1 + math.exp(-bo3_scale * logit[i, j]))
            p1[i, j] = (map_from_bo3(p3[i, j]) if bo1_scale is None
                        else 1 / (1 + math.exp(-bo1_scale * logit[i, j])))
    return p1, p3, states


def event_logits(eng: Engine, cfg: dict, teams: list[dict], on: date) -> tuple[np.ndarray, list[dict]]:
    """(blend logit matrix before the format scale, team states). teams: event-file entries in seed order."""
    # org_name: the name in Valve's data when the team plays under another name at this event
    states = [team_state(eng, t.get("org_name", t["name"]), t["roster"], on) for t in teams]
    n = len(teams)
    logit = np.zeros((n, n))
    w_own, w_vrs = cfg["blend"]["own"], cfg["blend"]["vrs"]
    for i in range(n):
        for j in range(n):
            if i != j:
                si, sj = states[i], states[j]
                z = LN10_400 * (si["rating"] - sj["rating"]) * math.exp(-(si["vol"] + sj["vol"]))
                v = LN10_400 * (teams[i]["vrs_points"] - teams[j]["vrs_points"])
                logit[i, j] = w_own * z + w_vrs * v
    return logit, states
