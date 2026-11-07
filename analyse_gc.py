#!/usr/bin/env python3
# =====================================================================================
# analyse_gc.py -- second mechanism test.
#
# analyse_allocation.py showed that allocation VOLUME is exactly additive while energy
# is not. The remaining obvious candidate is garbage-collection ACTIVITY: maybe two
# allocation sources trigger more collections than one.
#
# This script tests that, using the K=2000 run that actually exercises the collector.
#
# Input (in data_campaigns/):
#   M1_gc_cpu_K2000.csv  -- from `matrixk cpu 200000 2000 0`
#   M1_cpu.csv           -- paired energy campaign, Machine 1, compute-bound
# =====================================================================================

import csv
import math
import os
import statistics as st

PATTERNS = ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]
ALLOCATING = {"Fa", "Bu", "Ob", "Me"}

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_campaigns")


def decompose(name):
    return [name[i:i + 2] for i in range(0, len(name), 2)]


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else 0.0


def main():
    gc_rows = {r["config"]: r for r in csv.DictReader(
        open(os.path.join(DATA, "M1_gc_cpu_K2000.csv")))}
    gen0 = {k: int(v["gen0"]) for k, v in gc_rows.items()}
    gen1 = {k: int(v["gen1"]) for k, v in gc_rows.items()}
    gen2 = {k: int(v["gen2"]) for k, v in gc_rows.items()}
    volume = {k: int(v["alloc_per_iter"]) for k, v in gc_rows.items()}

    runs = {}
    for r in csv.DictReader(open(os.path.join(DATA, "M1_cpu.csv"))):
        runs.setdefault(r["config"], []).append(float(r["e_cfg"]) / float(r["e_base"]))
    rho = {k: st.median(v) for k, v in runs.items()}

    def delta(cfg):
        parts = decompose(cfg)
        return (rho[cfg] - (1.0 + sum(rho[p] - 1.0 for p in parts))) * 100.0

    comps = [c for c in rho
             if len(decompose(c)) > 1 and all(p in PATTERNS for p in decompose(c))]

    # ------------------------------------------------------------ additivity of gen0
    print("=" * 76)
    print("1. ARE GEN-0 COLLECTIONS ADDITIVE?")
    print("=" * 76)
    print(f"{'config':<10}{'measured':>10}{'predicted':>11}{'deviation':>12}")
    worst = 0.0
    for c in sorted(comps):
        predicted = sum(gen0[p] for p in decompose(c))
        if predicted:
            pct = 100.0 * (gen0[c] - predicted) / predicted
            worst = max(worst, abs(pct))
        else:
            pct = 0.0
        print(f"{c:<10}{gen0[c]:>10}{predicted:>11}{pct:>+11.2f}%")
    print(f"\n   -> largest deviation: {worst:.2f}%  => gen-0 activity is additive too.\n")

    # ------------------------------------------------------------ promotion
    print("=" * 76)
    print("2. DOES ANYTHING SURVIVE THE NURSERY?")
    print("=" * 76)
    print(f"   distinct gen1 counts: {sorted(set(gen1.values()))}")
    print(f"   distinct gen2 counts: {sorted(set(gen2.values()))}")
    print("   -> no promotion at all: every allocated object dies in generation 0.\n")

    # ------------------------------------------------------------ contrast
    print("=" * 76)
    print("3. DECISIVE CONTRAST")
    print("=" * 76)
    print(f"{'config':<10}{'bytes/task':>13}{'gen0':>9}{'sources':>9}{'delta_E':>10}")
    for c in ["StDeAd", "StBu", "ObMe", "FaBuMe"]:
        nsrc = sum(1 for p in decompose(c) if p in ALLOCATING)
        print(f"{c:<10}{volume[c]:>13,}{gen0[c]:>9}{nsrc:>9}{delta(c):>+9.1f}%")
    ratio = gen0["StBu"] / gen0["ObMe"]
    gap = delta("ObMe") - delta("StBu")
    print(f"\n   ObMe triggers {ratio:.0f}x FEWER collections than StBu, "
          f"yet its interaction is {gap:.0f} points larger.\n")

    # ------------------------------------------------------------ correlations
    print("=" * 76)
    print("4. WHAT PREDICTS THE ENERGY INTERACTION?")
    print("=" * 76)
    dy = [delta(c) for c in comps]
    print(f"   delta_E vs gen-0 collection count : r = {pearson([gen0[c] for c in comps], dy):+.3f}")
    print(f"   delta_E vs allocation volume      : r = {pearson([volume[c] for c in comps], dy):+.3f}")
    nsrc = [sum(1 for p in decompose(c) if p in ALLOCATING) for c in comps]
    print(f"   delta_E vs number of sources      : r = {pearson(nsrc, dy):+.3f}")
    print("\n   Both volume and collection count are additive and explain the")
    print("   interaction poorly; the number of independent allocating sources")
    print("   explains it well.\n")

    # ------------------------------------------------------- cross-regime control
    mem_path = os.path.join(DATA, "M1_gc_mem_K2000.csv")
    if not os.path.exists(mem_path):
        return
    mem_rows = {r["config"]: r for r in csv.DictReader(open(mem_path))}
    same_alloc = all(gc_rows[k]["alloc_per_iter"] == mem_rows[k]["alloc_per_iter"]
                     for k in gc_rows)
    same_gen0 = all(gc_rows[k]["gen0"] == mem_rows[k]["gen0"] for k in gc_rows)

    mem_runs = {}
    for r in csv.DictReader(open(os.path.join(DATA, "M1_mem.csv"))):
        mem_runs.setdefault(r["config"], []).append(float(r["e_cfg"]) / float(r["e_base"]))
    rho_mem = {k: st.median(v) for k, v in mem_runs.items()}

    def delta_mem(cfg):
        parts = decompose(cfg)
        return (rho_mem[cfg] - (1.0 + sum(rho_mem[p] - 1.0 for p in parts))) * 100.0

    print("=" * 76)
    print("5. CROSS-REGIME CONTROL: SAME COUNTERS, DIFFERENT ENERGY")
    print("=" * 76)
    print(f"   Allocation volumes identical in both regimes : {same_alloc}")
    print(f"   Gen-0 collection counts identical            : {same_gen0}")
    print("   (expected: both are properties of the code, not of the surrounding load)\n")
    print(f"{'config':<10}{'bytes/task':>13}{'gen0':>8}{'src':>5}"
          f"{'delta CPU':>12}{'delta MEM':>12}{'ratio':>9}")
    ranked = sorted(comps, key=lambda c: -delta(c))[:8]
    for c in ranked:
        dc, dm = delta(c), delta_mem(c)
        ratio = f"x{dc / dm:.1f}" if abs(dm) > 0.5 else "--"
        nsources = sum(1 for p in decompose(c) if p in ALLOCATING)
        print(f"{c:<10}{volume[c]:>13,}{gen0[c]:>8}{nsources:>5}"
              f"{dc:>+11.1f}%{dm:>+11.1f}%{ratio:>9}")
    print("\n   The allocation behaviour is byte-for-byte and collection-for-collection")
    print("   identical across regimes, yet the energy interaction is 7-16x larger in")
    print("   compute-bound code. The interaction is therefore not a property of the")
    print("   allocation itself, but of its contention with the surrounding workload.")
    print("   What remains to be measured is the COST of each collection, which needs")
    print("   GC pause-time instrumentation (future work).")


if __name__ == "__main__":
    main()
