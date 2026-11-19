"""Step 8, part 1: do map-specific offsets predict map results better?

The gatekeeper test, with the map that was played known. For every LAN map
between HLTV top-50 teams whose series is linked to a Valve match:
  p0 = map win probability from Model v1 (blend logit before the match ->
       BO3 probability -> map probability by independent maps)
  p  = p0 adjusted by the team's map offsets (pickem/maps.py)
eta and the half-life are tuned on training maps (from 2024-12, when the
HLTV file starts, to 2025-05); the offsets are kept only if p beats p0 on
validation maps (2025-06 to 2025-10) by more than 2 standard errors
(paired per-map log loss). The test period is not used. If this fails, no
veto model can help, and the map model stops here.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem.evaluate import PointsHistory  # noqa: E402
from pickem.history import load_history  # noqa: E402
from pickem.maps import MapOffsets  # noqa: E402
from pickem.model_v1 import LN10_400, Engine  # noqa: E402
from pickem.predict import load_config  # noqa: E402
from pickem.uncertainty import map_from_bo3_array  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VAL_START, TEST_START = date(2025, 6, 1), date(2025, 11, 1)
ETAS = [0.0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5]
HALF_LIVES = [60, 120, 240, 480, math.inf]
CLEAR = 2.0


def map_rows():
    """(date, team A id, team B id, map, A won, p0) per map, in time order; A = Valve's series winner side."""
    params, cfg = load_config(ROOT)
    s = json.loads((ROOT / "data/processed/bo_scales.json").read_text(encoding="utf-8"))["bo3_scale"]
    w_own, w_vrs = cfg["blend"]["own"], cfg["blend"]["vrs"]
    h = load_history(ROOT)
    points = PointsHistory(ROOT / "data/processed/vrs_points.csv")
    eng = Engine(params, h.regions, h.players)
    rows = []
    for i, m in enumerate(h.inputs):
        pred = eng.process(m)
        ser = h.links.get(i)
        if ser is None:
            continue
        rec = h.matches[i]
        pw, pl = points.lookup(rec.date, rec.winner, rec.winner_roster), points.lookup(rec.date, rec.loser, rec.loser_roster)
        if not (pw and pl):
            continue
        logit = w_own * pred.z + w_vrs * LN10_400 * (pw[0] - pl[0])
        q = 1.0 / (1.0 + math.exp(-s * logit))
        p0 = float(map_from_bo3_array(np.array([q]))[0])         # P(series winner's side wins a map)
        for mp in sorted(ser.maps, key=lambda x: x.map_id):
            a_is_1 = mp.team1_id == ser.team_a_id
            a_won = (mp.team1_rounds > mp.team2_rounds) == a_is_1
            rows.append((mp.date, ser.team_a_id, ser.team_b_id, mp.map, a_won, p0))
    rows.sort(key=lambda r: r[0])
    return rows, h


def run(rows, eta, half_life):
    """Per-map log loss with offsets and without, and the period of each map."""
    mo = MapOffsets(eta, half_life)
    ll, ll0, per = [], [], []
    for d, a, b, game_map, a_won, p0 in rows:
        p = mo.predict(p0, a, b, game_map, d)
        y = 1.0 if a_won else 0.0
        ll.append(-(y * math.log(p) + (1 - y) * math.log(1 - p)))
        ll0.append(-(y * math.log(p0) + (1 - y) * math.log(1 - p0)))
        per.append("train" if d < VAL_START else "val" if d < TEST_START else "test")
        mo.update(a, b, game_map, d, a_won, p)
    return np.array(ll), np.array(ll0), np.array(per)


def main():
    rows, h = map_rows()
    per = np.array(["train" if r[0] < VAL_START else "val" if r[0] < TEST_START else "test" for r in rows])
    print(f"maps with a linked series and VRS points: {len(rows):,} (train {np.sum(per == 'train'):,}, "
          f"val {np.sum(per == 'val'):,}; test not scored)")
    best = None
    print("\ntuning on training maps: gain = log loss without offsets minus with (positive = offsets help)")
    for hl in HALF_LIVES:
        line = []
        for eta in ETAS:
            ll, ll0, p = run(rows, eta, hl)
            tr = p == "train"
            gain = float((ll0[tr] - ll[tr]).mean())
            line.append(f"{gain:+.4f}")
            if best is None or gain > best[0]:
                best = (gain, eta, hl)
        print(f"  half-life {hl:>5} days: " + "  ".join(f"eta {e}: {g}" for e, g in zip(ETAS, line)))
    _, eta, hl = best
    print(f"\nbest on training: eta {eta}, half-life {hl} days")
    ll, ll0, p = run(rows, eta, hl)
    va = p == "val"
    diff = ll0[va] - ll[va]
    gain, se = float(diff.mean()), float(diff.std(ddof=1) / math.sqrt(va.sum()))
    verdict = "KEEP (clear gain)" if gain > CLEAR * se else "drop (no clear effect)" if gain > -CLEAR * se \
        else "drop (it makes predictions worse)"
    print(f"VALIDATION ({va.sum():,} maps): log loss {ll0[va].mean():.4f} without offsets, {ll[va].mean():.4f} with; "
          f"gain {gain:+.4f} +/- {se:.4f} ({gain / se if se else 0:+.1f} SE)  -> {verdict}")


if __name__ == "__main__":
    main()
