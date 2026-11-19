"""Step 7: how far is a team's true strength at an event from our estimate?

Measured on HLTV-linked LAN events (both teams HLTV top 50) in the training
and validation periods; the test period is not used.

Method:
  1. Run Model v1 over the history. For each event, freeze each team's
     rating at its first match there, as the simulator does for a whole
     stage, and predict every match of that event from the frozen ratings
     (VRS points as usual; BO1 from BO3 by independent maps).
  2. If a team is under- or over-rated at an event, its residuals there
     (result minus prediction) lean the same way. With a per-team offset
     e ~ N(0, sigma^2) in blend-logit units, two matches k, l of the same
     team at the same event have E[r_k r_l] ~ g_k g_l sigma^2, where g is
     how much the win probability moves per unit of e. sigma^2 is fitted to
     the products r_k r_l (weighted least squares, weights 1 / (v_k v_l),
     v = p(1 - p)).
  3. Standard error by resampling whole events (2,000 times).

Writes data/processed/uncertainty.json, used by scripts/run_stage.py.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem.evaluate import PointsHistory  # noqa: E402
from pickem.history import load_history  # noqa: E402
from pickem.model_v1 import LN10_400, Engine  # noqa: E402
from pickem.predict import load_config  # noqa: E402
from pickem.uncertainty import map_from_bo3_array  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TRAIN_START, VAL_START, TEST_START = date(2024, 8, 6), date(2025, 6, 1), date(2025, 11, 1)
FEW_MATCHES = 60  # "few matches": the team had played fewer than this when the event began


def prob(logit: float, best_of: int, s: float) -> tuple[float, float]:
    """(win probability, its change per unit of strength offset) for side A."""
    q = 1.0 / (1.0 + math.exp(-s * logit))
    if best_of == 1:
        p = float(map_from_bo3_array(np.array([q]))[0])
        return p, s * q * (1 - q) / (6 * p * (1 - p))
    return q, s * q * (1 - q)


def groups(records: list, s: float, a_won: np.ndarray) -> dict:
    """event -> team -> [(residual, g, v)] for each subset, from predictions and outcomes."""
    out = {k: defaultdict(lambda: defaultdict(list)) for k in ("all", "train", "val", "few", "many")}
    for (event, a, b, logit, bo, few_a, few_b, period), won in zip(records, a_won):
        p, g = prob(logit, bo, s)
        r = (1.0 if won else 0.0) - p
        for tid, sign, few in ((a, 1.0, few_a), (b, -1.0, few_b)):
            row = (sign * r, g, p * (1 - p))
            for key in ("all", period, "few" if few else "many"):
                out[key][event][tid].append(row)
    return out


def recovery_check(records: list, s: float, true_sigma: float, reps: int = 30, seed: int = 11) -> tuple[float, float]:
    """Simulate these matches with a known spread; (mean, sd) of the sigma^2 estimate."""
    rng = np.random.default_rng(seed)
    est = []
    for _ in range(reps):
        e = defaultdict(lambda: rng.normal(0.0, true_sigma))
        won = []
        for event, a, b, logit, bo, *_ in records:
            p, _ = prob(logit + e[(event, a)] - e[(event, b)], bo, s)
            won.append(rng.random() < p)
        num, den, _ = estimate(groups(records, s, np.array(won))["all"])
        est.append(num / den)
    return float(np.mean(est)), float(np.std(est, ddof=1))


def estimate(events: dict) -> tuple[float, float, int]:
    """(num, den, pairs) summed over events -> sigma^2 = num / den."""
    num = den = 0.0
    pairs = 0
    for groups in events.values():
        for rows in groups.values():
            for a in range(len(rows)):
                for b in range(a + 1, len(rows)):
                    (r1, g1, v1), (r2, g2, v2) = rows[a], rows[b]
                    w = 1.0 / (v1 * v2)
                    num += w * r1 * r2 * g1 * g2
                    den += w * (g1 * g2) ** 2
                    pairs += 1
    return num, den, pairs


def raw_with_se(events: dict, boot: int = 2000, seed: int = 7) -> tuple[float, float]:
    """sigma^2 estimate without the floor at 0, and its standard error (events resampled)."""
    parts = [estimate({k: events[k]}) for k in events]
    nums, dens = np.array([p[0] for p in parts]), np.array([p[1] for p in parts])
    rng = np.random.default_rng(seed)
    draws = [nums[i].sum() / dens[i].sum() for i in (rng.integers(0, len(parts), len(parts)) for _ in range(boot))]
    return float(nums.sum() / dens.sum()), float(np.std(draws, ddof=1))


def sigma_with_se(events: dict, boot: int = 2000, seed: int = 7) -> tuple[float, float, int]:
    keys = list(events)
    parts = [estimate({k: events[k]}) for k in keys]
    num = sum(p[0] for p in parts)
    den = sum(p[1] for p in parts)
    pairs = sum(p[2] for p in parts)
    rng = np.random.default_rng(seed)
    nums, dens = np.array([p[0] for p in parts]), np.array([p[1] for p in parts])
    draws = []
    for _ in range(boot):
        idx = rng.integers(0, len(keys), len(keys))
        draws.append(math.sqrt(max(nums[idx].sum() / dens[idx].sum(), 0.0)))
    return math.sqrt(max(num / den, 0.0)), float(np.std(draws, ddof=1)), pairs


def main():
    params, cfg = load_config(ROOT)
    bo = json.loads((ROOT / "data/processed/bo_scales.json").read_text(encoding="utf-8"))
    s = bo["bo3_scale"]
    w_own, w_vrs = cfg["blend"]["own"], cfg["blend"]["vrs"]
    h = load_history(ROOT)
    if not h.links:
        sys.exit("no HLTV links: put the HLTV map file at data/raw/hltv/maps_lan_top50.csv")
    points = PointsHistory(ROOT / "data/processed/vrs_points.csv")
    eng = Engine(params, h.regions, h.players)

    frozen = {}                                   # (event, team id) -> (rating, matches played) at its first match
    records, formats = [], defaultdict(int)
    for i, m in enumerate(h.inputs):
        before = {}
        for name, lineup in ((m.winner, m.winner_lineup), (m.loser, m.loser_lineup)):
            tid, _ = eng.find(name, frozenset(p.lower() for p in lineup) if lineup else None)
            before[name] = eng.teams[tid].played if tid is not None else 0
        pred = eng.process(m)
        ser = h.links.get(i)
        if ser is None:
            continue
        fa = frozen.setdefault((ser.event_id, pred.team_a), (pred.rating_a, before[m.winner]))
        fb = frozen.setdefault((ser.event_id, pred.team_b), (pred.rating_b, before[m.loser]))
        if not (TRAIN_START <= m.date < TEST_START):
            continue
        rec = h.matches[i]
        pw, pl = points.lookup(rec.date, rec.winner, rec.winner_roster), points.lookup(rec.date, rec.loser, rec.loser_roster)
        if not (pw and pl):
            continue
        logit = w_own * LN10_400 * (fa[0] - fb[0]) + w_vrs * LN10_400 * (pw[0] - pl[0])
        formats[ser.best_of] += 1
        records.append((ser.event_id, pred.team_a, pred.team_b, logit, ser.best_of,
                        fa[1] < FEW_MATCHES, fb[1] < FEW_MATCHES, "train" if m.date < VAL_START else "val"))

    n_used = len(records)
    subsets = groups(records, s, np.ones(n_used, dtype=bool))
    print(f"HLTV-linked LAN matches used (training + validation, both teams VRS-ranked): {n_used:,} "
          f"(BO1 {formats[1]}, BO3 {formats[3]}, BO5 {formats[5]}); events {len(subsets['all'])}")
    print(f"BO3 scale {s:.3f}; blend own {w_own:.3f}, VRS {w_vrs:.3f}\n")
    print("sigma = spread of a team's strength at an event around our estimate (blend-logit units)")
    results = {}
    for key, label in [("all", "all"), ("train", "training events"), ("val", "validation events"),
                       ("few", f"teams with < {FEW_MATCHES} matches"), ("many", f"teams with >= {FEW_MATCHES} matches")]:
        sig, se, pairs = sigma_with_se(subsets[key])
        results[key] = (sig, se, pairs)
        elo = sig / (w_own * LN10_400)            # the same spread as rating points of our own rating
        print(f"  {label:<28} sigma = {sig:.3f} +/- {se:.3f}   (about {elo:.0f} rating points; "
              f"{pairs:,} pairs of matches)")
    raw, raw_se = raw_with_se(subsets["all"])
    upper = math.sqrt(max(raw + 2 * raw_se, 0.0))
    print(f"\nsigma^2 without the floor at 0: {raw:+.4f} +/- {raw_se:.4f}; upper end (estimate + 2 SE): "
          f"sigma <= {upper:.3f} (about {upper / (w_own * LN10_400):.0f} rating points)")
    print("Can the method find a spread that is there? These matches simulated with a known sigma:")
    for true in (0.1, 0.2, 0.3, 0.5):
        mean, sd = recovery_check(records, s, true)
        print(f"  true sigma {true:.1f} (sigma^2 {true * true:.3f}): estimated sigma^2 {mean:.3f} +/- {sd:.3f}")
    sig, se, pairs = results["all"]
    t = math.sqrt(2) * s * sig
    print(f"\nFor two teams with offsets of this size, a 60% BO3 favourite is between "
          f"{1 / (1 + math.exp(-(math.log(1.5) - t))):.0%} and {1 / (1 + math.exp(-(math.log(1.5) + t))):.0%} "
          f"one standard deviation either way.")
    out = ROOT / "data/processed/uncertainty.json"
    out.write_text(json.dumps({
        "sigma": sig, "se": se, "sigma2_raw": raw, "sigma2_se": raw_se, "sigma_upper": upper, "pairs": pairs, "events": len(subsets["all"]), "matches": n_used,
        "fitted_on": f"HLTV-linked LAN events {TRAIN_START} to {TEST_START} (exclusive)",
        "subsets": {k: {"sigma": v[0], "se": v[1], "pairs": v[2]} for k, v in results.items()},
    }, indent=2), encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
