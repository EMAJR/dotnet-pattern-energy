#!/usr/bin/env python3
# =====================================================================================
# analyse_bootstrap.py -- SINGLE SOURCE OF TRUTH for every number in the manuscript.
#
# Reads the raw paired replication CSVs (columns: rep,config,e_base,e_cfg) and emits,
# for each of the four campaigns:
#   - the isolated pattern signatures rho_p
#   - for each of the 26 compositions: rho_C, rho_additive, delta, bootstrap SE(delta),
#     the z statistic, the Bonferroni verdict and the 95% bootstrap percentile interval
#   - the significance counts and the dose-response medians
# Also writes LaTeX-ready tables.
#
# Statistical definition (must match Section 3.6 of the paper):
#   rho          = median over n>=15 paired runs of (e_cfg / e_base)
#   rho_additive = 1 + sum_p (rho_p - 1)
#   delta        = rho_C - rho_additive
#   SE(delta)    = std-dev of B=4000 bootstrap replicates, resampling with replacement
#                  the n runs of the composition AND of each constituent pattern
#   significant  <=> |delta| > z * SE(delta),  z = 3.098  (Bonferroni, alpha = 0.05/26)
#
# Usage:  python3 analyse_bootstrap.py
# =====================================================================================

import csv
import os
import statistics as st
import random

# ------------------------------------------------------------------ configuration
PATTERNS = ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]
ALLOCATING = {"Fa", "Bu", "Ob", "Me"}          # heap-allocating patterns
INDIRECTION = {"St", "De", "Ad"}               # pure-indirection patterns

B = 20000                                      # bootstrap replicates (high: we need extreme percentiles)
ALPHA_FAMILY = 0.05
N_COMPARISONS = 26
ALPHA = ALPHA_FAMILY / N_COMPARISONS           # 0.0019231
Z_BONFERRONI = 3.098                           # two-sided normal quantile at ALPHA
SEED = 42

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_campaigns")

# Campaigns of record. Provenance is pinned here and nowhere else.
#   M1 = Intel i7-5600U  (Broadwell, 2C/4T, 4 MB L3)   -- run 2026-09-05, governor locked
#   M2 = Intel i5-1145G7 (Tiger Lake, 4C/8T, 8 MB L3)  -- run 2026-09-24, governor locked
# The 2026-09-06 M2 campaign is NOT used: its machine_info reports the CPU scaling at 30%,
# i.e. the performance governor was not in force. It is kept on disk for the record only.
CAMPAIGNS = [
    ("M1-CPU", "M1_cpu.csv"),
    ("M1-MEM", "M1_mem.csv"),
    ("M2-CPU", "M2_cpu.csv"),
    ("M2-MEM", "M2_mem.csv"),
]


# ------------------------------------------------------------------ helpers
def decompose(config_name):
    """'FaBuMe' -> ['Fa', 'Bu', 'Me'].  Config names are concatenated 2-letter codes."""
    return [config_name[i:i + 2] for i in range(0, len(config_name), 2)]


def load_ratios(path):
    """Return {config: [paired ratio per rep]} from a raw replication CSV."""
    ratios = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            r = float(row["e_cfg"]) / float(row["e_base"])
            ratios.setdefault(row["config"], []).append(r)
    return ratios


def bootstrap_delta(comp_runs, pattern_runs, rng):
    """One bootstrap replicate of delta: resample composition and each pattern."""
    rho_c = st.median(rng.choices(comp_runs, k=len(comp_runs)))
    additive = 1.0 + sum(
        st.median(rng.choices(runs, k=len(runs))) - 1.0 for runs in pattern_runs
    )
    return rho_c - additive


def percentile(sorted_values, q):
    """Linear-interpolated percentile, q in [0, 1]."""
    if not sorted_values:
        return float("nan")
    idx = q * (len(sorted_values) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


# ------------------------------------------------------------------ analysis
def analyse(label, path):
    ratios = load_ratios(path)
    rho = {cfg: st.median(v) for cfg, v in ratios.items()}
    rng = random.Random(SEED)

    results = []
    for cfg, runs in ratios.items():
        parts = decompose(cfg)
        if len(parts) < 2:
            continue                                   # isolated pattern, not a composition
        if not all(p in PATTERNS for p in parts):
            continue                                   # unknown code, skip defensively

        additive = 1.0 + sum(rho[p] - 1.0 for p in parts)
        delta = rho[cfg] - additive

        pattern_runs = [ratios[p] for p in parts]
        replicates = sorted(
            bootstrap_delta(runs, pattern_runs, rng) for _ in range(B)
        )
        se = st.stdev(replicates)
        z = delta / se if se > 0 else 0.0
        # Percentile interval taken AT THE BONFERRONI LEVEL, so that it is directly
        # comparable with the |delta| > z*SE rule. A plain 95% interval would be a
        # different test and would disagree on borderline cases by construction.
        ci_lo = percentile(replicates, ALPHA / 2)
        ci_hi = percentile(replicates, 1 - ALPHA / 2)

        results.append({
            "config": cfg,
            "k": len(parts),
            "n_alloc": sum(1 for p in parts if p in ALLOCATING),
            "rho": rho[cfg],
            "additive": additive,
            "delta": delta,
            "se": se,
            "z": z,
            "significant": abs(delta) > Z_BONFERRONI * se,
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
            "n_reps": len(runs),
            # percentile-interval verdict, used as a robustness check
            "sig_by_ci": not (ci_lo <= 0.0 <= ci_hi),
        })

    results.sort(key=lambda r: -r["delta"])
    return rho, results


def report(label, rho, results):
    n_reps = st.median([r["n_reps"] for r in results])
    print("=" * 96)
    print(f"{label}   (n = {int(n_reps)} paired runs per configuration, B = {B} bootstrap replicates)")
    print("=" * 96)

    print("\n-- Isolated signatures rho_p --")
    for p in PATTERNS:
        if p in rho:
            kind = "allocating " if p in ALLOCATING else "indirection"
            print(f"   {p}  {kind}  rho = {rho[p]:.3f}   ({(rho[p] - 1) * 100:+.1f}%)")

    print("\n-- Compositions --")
    BONF_LBL = 'Bonf. interval (%)'
    hdr = f"{'config':<9}{'k':>2}{'A':>3}{'rho':>9}{'addit.':>9}{'delta%':>10}{'SE%':>7}{'z':>8}  {'Bonf':<5}{BONF_LBL:>20}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        verdict = "YES" if r["significant"] else "."
        flag = "" if r["significant"] == r["sig_by_ci"] else "  <-- CI disagrees"
        print(f"{r['config']:<9}{r['k']:>2}{r['n_alloc']:>3}"
              f"{r['rho']:>9.3f}{r['additive']:>9.3f}"
              f"{r['delta'] * 100:>+10.1f}{r['se'] * 100:>7.1f}{r['z']:>8.2f}  {verdict:<5}"
              f"[{r['ci_lo'] * 100:>+6.1f},{r['ci_hi'] * 100:>+6.1f}]{flag}")

    n_sig = sum(1 for r in results if r["significant"])
    n_super = sum(1 for r in results if r["significant"] and r["delta"] > 0)
    n_sub = n_sig - n_super
    print(f"\n   -> {len(results)} compositions | {n_sig} significant after Bonferroni "
          f"({n_super} super-additive, {n_sub} sub-additive)")

    disagree = [r["config"] for r in results if r["significant"] != r["sig_by_ci"]]
    print(f"   -> percentile-interval robustness check: "
          f"{'classification unchanged for all compositions' if not disagree else 'DISAGREEMENT on ' + ', '.join(disagree)}")

    print("\n-- Dose-response: median delta by number of heap-allocating patterns --")
    for a in range(4):
        grp = [r["delta"] * 100 for r in results if r["n_alloc"] == a]
        if grp:
            print(f"   {a} allocating : n = {len(grp):>2}   median delta = {st.median(grp):>+6.1f}%")

    ctrl = next((r for r in results if r["config"] == "StDeAd"), None)
    if ctrl:
        print(f"\n-- Negative control StDeAd : delta = {ctrl['delta'] * 100:+.1f}%  "
              f"(2SE = {ctrl['se'] * 200:.1f}%, z = {ctrl['z']:.2f}) -> "
              f"{'SIGNIFICANT' if ctrl['significant'] else 'not significant'}")
    print()


def write_latex(all_results, out_path):
    """Emit a LaTeX table per campaign, ready to paste."""
    with open(out_path, "w") as f:
        f.write("% Auto-generated by analyse_bootstrap.py -- DO NOT EDIT BY HAND.\n")
        f.write("% Regenerate after any change to the raw data or the statistical definition.\n\n")
        for label, _, results in all_results:
            f.write(f"% ---------------- {label} ----------------\n")
            f.write("\\begin{table}[t]\n\\centering\\small\n")
            f.write(f"\\caption{{Interaction $\\delta$ per composition, {label}. "
                    f"Bootstrap SE over $B={B}$ replicates; "
                    f"significance under Bonferroni correction ($z>{Z_BONFERRONI}$).}}\n")
            f.write(f"\\label{{tab:delta_{label.replace('-', '_').lower()}}}\n")
            f.write("\\begin{tabular}{lccrrrc}\n\\toprule\n")
            f.write("Composition & $k$ & Alloc. & $\\rho$ & $\\delta$ (\\%) "
                    "& $2\\,\\mathrm{SE}$ (\\%) & Sig. \\\\\n\\midrule\n")
            for r in results:
                mark = "$\\checkmark$" if r["significant"] else "--"
                f.write(f"\\texttt{{{r['config']}}} & {r['k']} & {r['n_alloc']} & "
                        f"{r['rho']:.3f} & {r['delta'] * 100:+.1f} & "
                        f"{r['se'] * 200:.1f} & " + mark + " \\\\\n")
            n_sig = sum(1 for r in results if r["significant"])
            n_super = sum(1 for r in results if r["significant"] and r["delta"] > 0)
            f.write("\\bottomrule\n\\end{tabular}\n")
            f.write(f"% {n_sig}/{len(results)} significant, {n_super} super-additive\n")
            f.write("\\end{table}\n\n")
    print(f"LaTeX tables written to: {out_path}")


def main():
    all_results = []
    for label, filename in CAMPAIGNS:
        path = os.path.join(DATA, filename)
        if not os.path.exists(path):
            print(f"!! missing file, campaign skipped: {filename}")
            continue
        rho, results = analyse(label, path)
        report(label, rho, results)
        all_results.append((label, rho, results))

    if all_results:
        write_latex(all_results, os.path.join(HERE, "tables_delta_auto.tex"))


if __name__ == "__main__":
    main()
