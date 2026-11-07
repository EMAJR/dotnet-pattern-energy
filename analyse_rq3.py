#!/usr/bin/env python3
# RQ3 rebuilt on the M1 campaigns that captured time (M1_cpu_ET, M1_mem_ET), with the idle
# package power MEASURED by B0 (median of 3 x 60 s) and a sensitivity grid around it.
import csv, os, random, statistics as st, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data_campaigns")
OUT = os.path.join(HERE, "phaseB"); os.makedirs(OUT, exist_ok=True)
spec = importlib.util.spec_from_file_location("ab", os.path.join(HERE, "analyse_bootstrap.py"))
ab = importlib.util.module_from_spec(spec); spec.loader.exec_module(ab)
Z, ALPHA = ab.Z_BONFERRONI, ab.ALPHA
def dec(s): return [s[i:i+2] for i in range(0, len(s), 2)]
idle = [float(r["idle_power_W"]) for r in csv.DictReader(open(os.path.join(DATA, "phaseB", "B0_idle_machine1.csv")))]
P_MEAS = st.median(idle)
GRID = [0.0, P_MEAS, max(idle), 0.80, 2.26]
rows = []; summary = []
for lab, fn in (("M1-CPU (re-run)", "M1_cpu_ET.csv"), ("M1-MEM (re-run)", "M1_mem_ET.csv")):
    raw = list(csv.DictReader(open(os.path.join(DATA, fn))))
    tb = st.median(float(r["t_base"]) for r in raw); eb = st.median(float(r["e_base"]) for r in raw)
    for P in GRID:
        R = {}
        for r in raw:
            num = float(r["e_cfg"]) - P * float(r["t_cfg"]); den = float(r["e_base"]) - P * float(r["t_base"])
            R.setdefault(r["config"], []).append(num / den)
        rho = {k: st.median(v) for k, v in R.items()}
        comps = [c for c in R if len(dec(c)) >= 2]
        rng = random.Random(1); nsup = nsub = rsup = rsub = 0
        for c in comps:
            d = rho[c] - (1 + sum(rho[p] - 1 for p in dec(c)))
            bs = sorted(ab.bootstrap_delta(R[c], [R[p] for p in dec(c)], rng) for _ in range(2000))
            se = st.stdev(bs); lo, hi = ab.percentile(bs, ALPHA/2), ab.percentile(bs, 1-ALPHA/2)
            zs = abs(d) > Z * se; rb = zs and not (lo <= 0 <= hi)
            nsup += zs and d > 0; nsub += zs and d < 0; rsup += rb and d > 0; rsub += rb and d < 0
            rows.append([lab, "%.3f" % P, c, "%+.1f" % (d * 100), "%.1f" % (2 * se * 100), int(zs), int(rb)])
        summary.append((lab, P, 100 * P * tb / eb, nsup, nsub, rsup, rsub))
with open(os.path.join(OUT, "RQ3_idle_rebuilt.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["campaign", "P_idle_W", "composition", "delta", "2SE", "sig_z", "sig_robust"]); w.writerows(rows)
print("P_idle measured on M1 (B0): runs %s W -> median %.3f W" % (", ".join("%.3f" % x for x in idle), P_MEAS))
print("%-16s %8s %16s %16s %16s" % ("campaign", "P_idle", "% of base energy", "z: super/sub", "robust: super/sub"))
for lab, P, frac, a, b, c, d in summary:
    print("%-16s %7.2fW %15.1f%% %10d / %-4d %10d / %-4d" % (lab, P, frac, a, b, c, d))
# figure
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
for ax, lab in zip(axes, ("M1-CPU (re-run)", "M1-MEM (re-run)")):
    S = [s for s in summary if s[0] == lab]
    x = range(len(S)); lbl = ["none" if s[1] == 0 else ("%.2f W\n(measured)" % s[1] if abs(s[1]-P_MEAS) < 1e-9 else "%.2f W" % s[1]) for s in S]
    ax.bar([i - 0.2 for i in x], [s[5] for s in S], 0.4, label="super-additive", color="#c0392b")
    ax.bar([i + 0.2 for i in x], [s[6] for s in S], 0.4, label="sub-additive", color="#2471a3")
    ax.set_xticks(list(x)); ax.set_xticklabels(lbl, fontsize=8); ax.set_title(lab.replace(" (re-run)", ""), fontsize=10)
    ax.set_xlabel("idle power subtracted", fontsize=9)
axes[0].set_ylabel("significant interactions (of 26)", fontsize=9); fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=2, fontsize=8, frameon=False, bbox_to_anchor=(0.5, 1.02))
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(os.path.join(HERE, "fig_idle_artifact_v2.pdf")); print("figure -> fig_idle_artifact_v2.pdf")
