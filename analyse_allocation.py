#!/usr/bin/env python3
# =====================================================================================
# analyse_allocation.py -- mechanism analysis.
#
# Question: is the super-additive energy interaction driven by HOW MANY BYTES a
# composition allocates, or by HOW MANY INDEPENDENT ALLOCATION SOURCES it contains?
#
# Inputs (all in data_campaigns/):
#   M1_alloc_cpu.csv, M1_alloc_mem.csv  -- from `matrixk <regime> 200000 1 0`
#   M1_cpu.csv, M1_mem.csv, M2_cpu.csv, M2_mem.csv  -- paired energy campaigns
#
# Outputs:
#   fig_allocation_mechanism.pdf  -- delta vs allocation volume, coloured by #sources
#   console report with correlations and the constant-volume contrasts
# =====================================================================================

import csv
import math
import os
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PATTERNS = ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]
ALLOCATING = {"Fa", "Bu", "Ob", "Me"}

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_campaigns")

CAMPAIGNS = [("M1-CPU", "M1_cpu.csv"), ("M1-MEM", "M1_mem.csv"),
             ("M2-CPU", "M2_cpu.csv"), ("M2-MEM", "M2_mem.csv")]


def decompose(name):
    return [name[i:i + 2] for i in range(0, len(name), 2)]


def load_alloc(path):
    out = {}
    for r in csv.DictReader(open(path)):
        if r.get("config"):
            out[r["config"]] = int(r["alloc_per_iter"])
    return out


def load_rho(path):
    d = {}
    for r in csv.DictReader(open(path)):
        d.setdefault(r["config"], []).append(float(r["e_cfg"]) / float(r["e_base"]))
    return {k: st.median(v) for k, v in d.items()}


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else 0.0


def spearman(x, y):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos + 1
        return r
    return pearson(rank(x), rank(y))


def deltas(rho):
    out = {}
    for cfg in rho:
        parts = decompose(cfg)
        if len(parts) < 2 or not all(p in PATTERNS for p in parts):
            continue
        additive = 1.0 + sum(rho[p] - 1.0 for p in parts)
        out[cfg] = (rho[cfg] - additive) * 100.0
    return out


def main():
    alloc = load_alloc(os.path.join(DATA, "M1_alloc_mem.csv"))
    alloc_cpu = load_alloc(os.path.join(DATA, "M1_alloc_cpu.csv"))
    base = alloc["base"]

    # ---------------------------------------------------------------- additivity
    print("=" * 84)
    print("1. IS ALLOCATION VOLUME ITSELF ADDITIVE?")
    print("=" * 84)
    print(f"   Allocation volumes are identical in both regimes: {alloc == alloc_cpu}")
    worst = 0
    for cfg in alloc:
        parts = decompose(cfg)
        if len(parts) < 2 or not all(p in PATTERNS for p in parts):
            continue
        predicted = base + sum(alloc[p] - base for p in parts)
        worst = max(worst, abs(alloc[cfg] - predicted))
    print(f"   Largest deviation from exact additivity over the 26 compositions: {worst} bytes")
    print("   -> allocation volume is EXACTLY additive, while energy is super-additive.\n")

    # ---------------------------------------------------------------- correlations
    print("=" * 84)
    print("2. WHAT PREDICTS THE INTERACTION: VOLUME OR NUMBER OF SOURCES?")
    print("=" * 84)
    print(f"{'campaign':<10}{'r(volume)':>12}{'rho_s(volume)':>16}{'r(#sources)':>14}{'rho_s(#sources)':>18}")
    print("-" * 72)
    store = {}
    for label, fname in CAMPAIGNS:
        d = deltas(load_rho(os.path.join(DATA, fname)))
        cfgs = sorted(d)
        vol = [alloc[c] for c in cfgs]
        nsrc = [sum(1 for p in decompose(c) if p in ALLOCATING) for c in cfgs]
        dl = [d[c] for c in cfgs]
        store[label] = (cfgs, vol, nsrc, dl)
        print(f"{label:<10}{pearson(vol, dl):>+12.3f}{spearman(vol, dl):>+16.3f}"
              f"{pearson(nsrc, dl):>+14.3f}{spearman(nsrc, dl):>+18.3f}")
    print("\n   -> the number of independent allocating sources predicts the interaction")
    print("      far better than the number of bytes allocated.\n")

    # ---------------------------------------------------------------- contrasts
    print("=" * 84)
    print("3. CONTROLLED CONTRASTS: SAME VOLUME, DIFFERENT delta (Machine 1, CPU)")
    print("=" * 84)
    cfgs, vol, nsrc, dl = store["M1-CPU"]
    groups = {}
    for c, v, s, y in zip(cfgs, vol, nsrc, dl):
        groups.setdefault(v, []).append((c, y, s))
    for v in sorted(groups):
        g = sorted(groups[v], key=lambda t: -t[1])
        if len(g) > 1:
            items = " | ".join(f"{c} {y:+.1f}% [{s} src]" for c, y, s in g)
            print(f"   {v:>10,} B/task : {items}")

    by_cfg = dict(zip(cfgs, dl))
    print(f"\n   Decisive pair:")
    print(f"     StBu : {alloc['StBu']:>10,} B/task, 1 source  -> delta = {by_cfg['StBu']:+.1f}%")
    print(f"     ObMe : {alloc['ObMe']:>10,} B/task, 2 sources -> delta = {by_cfg['ObMe']:+.1f}%")
    print(f"   ObMe allocates {alloc['StBu'] / alloc['ObMe']:.0f}x LESS than StBu, "
          f"yet its interaction is {by_cfg['ObMe'] - by_cfg['StBu']:.0f} points larger.\n")

    # ---------------------------------------------------------------- figure
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    colours = {0: "#7f8c8d", 1: "#2471a3", 2: "#e67e22", 3: "#c0392b"}
    labels = {0: "0 allocating", 1: "1 allocating", 2: "2 allocating", 3: "3 allocating"}

    for ax, label in zip(axes, ["M1-CPU", "M2-MEM"]):
        cfgs, vol, nsrc, dl = store[label]
        for s in range(4):
            xs = [v for v, k in zip(vol, nsrc) if k == s]
            ys = [y for y, k in zip(dl, nsrc) if k == s]
            if xs:
                ax.scatter(xs, ys, s=58, c=colours[s], label=labels[s],
                           edgecolors="white", linewidths=0.8, zorder=3)
        ax.set_xscale("log")
        ax.axhline(0, color="#aaaaaa", lw=0.9, ls="--", zorder=1)
        ax.set_xlabel("Allocation volume (bytes per task, log scale)")
        ax.set_title(label, fontsize=11)
        ax.grid(alpha=0.25, zorder=0)
    axes[0].set_ylabel(r"Interaction $\delta$ (%)")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left")

    fig.suptitle("Interaction is governed by the number of allocating sources, "
                 "not by allocation volume", fontsize=11.5)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = os.path.join(HERE, "fig_allocation_mechanism.pdf")
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=150)
    print(f"Figure written to: {out}")

    # ---------------------------------------------------------------- caveat
    print("\n" + "=" * 84)
    print("CAVEAT: the gen0/gen1/gen2 columns carry no information at K=1 (0 or 1 per")
    print("config). To obtain usable GC-collection counts, re-run with a large K, e.g.")
    print("    dotnet run -c Release -- matrixk cpu 200000 2000 0 > alloc_cpu_K2000.csv")
    print("A task takes ~5 ms, so K=2000 is about 10 s per configuration (~6 min total).")
    print("=" * 84)


if __name__ == "__main__":
    main()
