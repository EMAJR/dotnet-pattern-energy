#!/usr/bin/env python3
"""Phase-2b analysis: resource signatures, interaction term delta, and the predictive law.

Pipeline
--------
1. Load one or more `matrix` CSVs (schema emitted by `proto matrix`), optionally prefixed
   with a replicate id (from the reps loop). Aggregate to ONE row per (config, regime) by
   MEDIAN across replicates.
2. Calibrate the per-pattern resource SIGNATURE on Order 0-1:
       s_alloc(DP) = alloc_per_iter(DP) - alloc_per_iter(base)
       s_disp (DP) = branch_misses_per_iter(DP) - ...(base)     [if a PMU CSV is merged]
   and the isolated dynamic energy  dE(DP) = E(DP) - E(base).
3. For every Order>=2 config, compute the interaction term against the additive null:
       delta = E(combo) - [ E(base) + sum_{DP in combo} dE(DP) ]
   Declared non-additive only if |delta| > noise_threshold (baseline repeatability).
4. Fit the resource-signature LAW (same-axis cross-terms; disjoint axes stay additive):
       delta_hat = g_alloc * SUM_{i<j} s_alloc_i*s_alloc_j  (+ g_disp * SUM_{i<j} s_disp_i*s_disp_j)
   Evaluate by Leave-One-Out CV the MAE gain vs the naive additive model (delta = 0).

Usage
-----
  python3 analyze.py matrix_cpu.csv                 # single regime
  python3 analyze.py matrix_mem.csv --pmu pmu_mem.csv --idle-power 3.2 --window-s 5
  python3 analyze.py reps_mem.csv                   # replicate-prefixed file (auto-detected)

No third-party dependencies (pure stdlib).
"""
from __future__ import annotations
import argparse, csv, math, statistics, sys
from itertools import combinations

PAT_CODES = ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]


# ---------------------------------------------------------------- helpers
def patterns_of(name):
    """Return the set of pattern codes present in a config name ('base' -> empty)."""
    if name == "base":
        return []
    return [c for c in PAT_CODES if c in name]


def order_of(name):
    return len(patterns_of(name))


def load_matrix(path):
    """Load a matrix CSV; auto-detect a leading replicate column. Returns list of dict rows."""
    rows = []
    with open(path, newline="") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        # a replicate-prefixed file has an extra first column before 'config'
        has_rep = header[0] != "config"
        cols = header[1:] if has_rep else header
        idx = {c: i for i, c in enumerate(cols)}
        for raw in rdr:
            if not raw:
                continue
            vals = raw[1:] if has_rep else raw
            if len(vals) < len(cols):
                continue
            rows.append({
                "config": vals[idx["config"]],
                "regime": vals[idx["regime"]],
                "energy_J": float(vals[idx["energy_J"]]) if vals[idx["energy_J"]] else float("nan"),
                "iters": float(vals[idx["iters"]]),
                "alloc_per_iter": float(vals[idx["alloc_per_iter"]]),
                "gen0": float(vals[idx["gen0"]]),
                "gen1": float(vals[idx["gen1"]]),
                "gen2": float(vals[idx["gen2"]]),
            })
    return rows


def aggregate(rows, idle_power=0.0, window_s=0.0):
    """Median across replicates -> {config: {...}}.

    KEY METRIC: energy PER TASK  (energy_op = energy_J / iters).
    Each Run(n) call is the SAME fixed workload (identical checksum), so energy_J/iters is
    the energy to accomplish one fixed task under a given config. This is the quantity that
    is meaningfully additive/non-additive. We do NOT use total energy over the fixed time
    window: that is proportional to average POWER, which saturates near TDP and produces a
    spurious systematic sub-additivity for every composition.
    """
    buckets = {}
    for r in rows:
        buckets.setdefault(r["config"], []).append(r)
    agg = {}
    for cfg, rs in buckets.items():
        eops = []
        for x in rs:
            if math.isnan(x["energy_J"]) or x["iters"] <= 0:
                continue
            e = x["energy_J"]
            if idle_power and window_s:                      # remove the idle floor over the window
                e = e - idle_power * window_s
            eops.append(e / x["iters"])                      # -> energy per fixed task
        energy_op = statistics.median(eops) if eops else float("nan")
        agg[cfg] = {
            "energy_op": energy_op,
            "alloc_per_iter": statistics.median([x["alloc_per_iter"] for x in rs]),
            "gen0": statistics.median([x["gen0"] for x in rs]),
            "gen1": statistics.median([x["gen1"] for x in rs]),
            "gen2": statistics.median([x["gen2"] for x in rs]),
            "n_reps": len(rs),
        }
    return agg


def merge_pmu(agg, pmu_path):
    """Merge branch-misses per iter from a PMU CSV (columns must include config, iters, branch_misses)."""
    try:
        pmu_rows = []
        with open(pmu_path, newline="") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                pmu_rows.append(r)
    except OSError:
        print("  [warn] PMU file not found: %s" % pmu_path)
        return
    buck = {}
    for r in pmu_rows:
        cfg = r.get("config")
        bm = r.get("branch_misses") or r.get("branch-misses")
        it = r.get("iters")
        if cfg and bm and it:
            buck.setdefault(cfg, []).append(float(bm) / float(it))
    for cfg, vals in buck.items():
        if cfg in agg:
            agg[cfg]["bm_per_iter"] = statistics.median(vals)


# ---------------------------------------------------------------- least squares
def lstsq(X, y):
    """Ordinary least squares via normal equations (X: list of feature-vectors, y: list)."""
    k = len(X[0]) if X else 0
    if k == 0:
        return []
    # A = X^T X (k x k), b = X^T y (k)
    A = [[sum(X[r][i] * X[r][j] for r in range(len(X))) for j in range(k)] for i in range(k)]
    b = [sum(X[r][i] * y[r] for r in range(len(X))) for i in range(k)]
    return solve(A, b)


def solve(A, b):
    """Gaussian elimination with partial pivoting; returns x for Ax=b (A square)."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-15:
            M[c][c] += 1e-12  # ridge nudge for singular/collinear systems
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        for r in range(n):
            if r == c:
                continue
            f = M[r][c] / piv
            for cc in range(c, n + 1):
                M[r][cc] -= f * M[c][cc]
    return [M[i][n] / M[i][i] for i in range(n)]


# ---------------------------------------------------------------- main analysis
def analyze(agg, noise_cv=0.041):
    if "base" not in agg:
        sys.exit("no 'base' config in data — cannot compute deltas.")
    E0 = agg["base"]["energy_op"]                 # energy per fixed task (J/op)
    A0 = agg["base"]["alloc_per_iter"]
    bm0 = agg["base"].get("bm_per_iter", 0.0)
    noise = abs(E0) * noise_cv  # practical-significance threshold from baseline repeatability

    # --- signatures & isolated energies (Order 1) ---
    sig = {}   # code -> {"dE","s_alloc","s_disp"}
    for cfg, d in agg.items():
        if order_of(cfg) == 1:
            code = patterns_of(cfg)[0]
            sig[code] = {
                "dE": d["energy_op"] - E0,
                "s_alloc": d["alloc_per_iter"] - A0,
                "s_disp": d.get("bm_per_iter", 0.0) - bm0,
            }

    # --- interaction term for Order >= 2 ---
    inter = []  # (cfg, order, E, add_pred, delta, x_alloc, x_disp)
    for cfg, d in agg.items():
        o = order_of(cfg)
        if o < 2:
            continue
        codes = patterns_of(cfg)
        if not all(c in sig for c in codes):
            continue  # need all singletons calibrated
        add_pred = E0 + sum(sig[c]["dE"] for c in codes)
        delta = d["energy_op"] - add_pred
        x_alloc = sum(sig[a]["s_alloc"] * sig[b]["s_alloc"] for a, b in combinations(codes, 2))
        x_disp = sum(sig[a]["s_disp"] * sig[b]["s_disp"] for a, b in combinations(codes, 2))
        inter.append([cfg, o, d["energy_op"], add_pred, delta, x_alloc, x_disp])

    return E0, noise, sig, inter


def fit_law(inter, use_disp):
    """Fit delta ~ g_alloc*x_alloc (+ g_disp*x_disp) and LOOCV vs naive (delta=0)."""
    if len(inter) < 2:
        return None
    def feats(row):
        return [row[5], row[6]] if use_disp else [row[5]]
    y = [row[4] for row in inter]
    X = [feats(row) for row in inter]
    coef = lstsq(X, y)
    # LOOCV
    err_law, err_naive = [], []
    for i in range(len(inter)):
        Xtr = [feats(inter[j]) for j in range(len(inter)) if j != i]
        ytr = [inter[j][4] for j in range(len(inter)) if j != i]
        c = lstsq(Xtr, ytr)
        pred = sum(c[k] * feats(inter[i])[k] for k in range(len(c)))
        err_law.append(abs(inter[i][4] - pred))
        err_naive.append(abs(inter[i][4] - 0.0))  # additive null predicts delta=0
    return coef, statistics.mean(err_law), statistics.mean(err_naive)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", help="matrix CSV file(s)")
    ap.add_argument("--pmu", help="optional PMU CSV (branch_misses) to enable the dispatch axis")
    ap.add_argument("--idle-power", type=float, default=0.0, help="idle package power (W) to subtract")
    ap.add_argument("--window-s", type=float, default=0.0, help="measurement window length (s) for idle subtraction")
    ap.add_argument("--noise-cv", type=float, default=0.041, help="baseline energy CV (default 4.1%% from Phase 1)")
    args = ap.parse_args()

    rows = []
    for p in args.csv:
        rows += load_matrix(p)
    agg = aggregate(rows, args.idle_power, args.window_s)
    if args.pmu:
        merge_pmu(agg, args.pmu)
    use_disp = any("bm_per_iter" in d for d in agg.values())

    E0, noise, sig, inter = analyze(agg, args.noise_cv)
    SC = 1e3  # display energies per task in mJ/op (J/op x 1000)

    print("=" * 82)
    print("  Phase-2b analysis  |  metric = energy PER TASK (mJ/op)")
    print("  E_base = %.4f mJ/op  |  noise threshold = %.4f mJ/op  |  configs = %d"
          % (E0 * SC, noise * SC, len(agg)))
    print("=" * 82)

    print("\n  RESOURCE SIGNATURES (Order 1)")
    print("  %-3s %12s %14s %12s" % ("DP", "dE (mJ/op)", "s_alloc (B/it)", "s_disp"))
    for code in PAT_CODES:
        if code in sig:
            s = sig[code]
            print("  %-3s %12.4f %14.1f %12.1f" % (code, s["dE"] * SC, s["s_alloc"], s["s_disp"]))

    print("\n  INTERACTIONS (Order >= 2)   [* = |delta| exceeds noise]   (all in mJ/op)")
    print("  %-10s %2s %10s %10s %10s %s"
          % ("config", "o", "E", "add.pred", "delta", "class"))
    for row in sorted(inter, key=lambda r: -abs(r[4])):
        cfg, o, E, add, delta = row[0], row[1], row[2], row[3], row[4]
        sig_flag = "*" if abs(delta) > noise else " "
        cls = ("super-additif" if delta > noise else
               "sous-additif" if delta < -noise else "additif")
        print("  %-10s %2d %10.4f %10.4f %+10.4f %s%s" % (cfg, o, E * SC, add * SC, delta * SC, sig_flag, cls))

    res = fit_law(inter, use_disp)
    if res:
        coef, mae_law, mae_naive = res
        print("\n  PREDICTIVE LAW  (delta_hat = g_alloc*x_alloc%s)"
              % (" + g_disp*x_disp" if use_disp else ""))
        print("    g_alloc = %.4e%s" % (coef[0], ("   g_disp = %.4e" % coef[1]) if use_disp else ""))
        print("    LOOCV MAE  law   = %.4f mJ/op" % (mae_law * SC))
        print("    LOOCV MAE  naive = %.4f mJ/op  (additive null, delta=0)" % (mae_naive * SC))
        gain = 100 * (1 - mae_law / mae_naive) if mae_naive else 0.0
        print("    => MAE reduction vs additive null: %.1f%%" % gain)
    else:
        print("\n  [not enough Order>=2 configs to fit the predictive law]")


if __name__ == "__main__":
    main()
