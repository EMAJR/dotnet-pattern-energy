# =====================================================================================
# Revision 7 -- checks requested by the referee report on revision 6 (no new measurement).
#   R7-1  idle-power accounting on Machine 2 (measured idle power 1.82 W), both regimes
#   R7-3  retired-instruction surplus per call at the shared site (the transferable invariant)
#   R7-5  instruction surplus of the control under the default JIT configuration
#   R7-6  absolute interaction of FaBuMe in both regimes, code-A/B campaign (second estimate)
# Output: rev5/values_rev7.json and phaseR/RESULTATS_REV7.md
# Usage: python3 analyse_rev7.py
# =====================================================================================
import csv, os, json, statistics as st
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data_campaigns"); OUT = os.path.join(HERE, "rev5")
Z = 3.0976; A = 0.05 / 26; rng = np.random.default_rng(7); B = 20000
def dec(c): return [c[i:i + 2] for i in range(0, len(c), 2)]
V = {}; md = ["# Calculs de la révision 7\n"]

# R7-1 ----------------------------------------------------------------------------------
idle_m2 = st.median(float(r["idle_power_W"]) for r in csv.DictReader(open(os.path.join(D, "M2_results_20261019/M2_B0_idle_machine2.csv"))))
def load(f, P):
    R = {}
    for r in csv.DictReader(open(os.path.join(D, f))):
        R.setdefault(r["config"], []).append((float(r["e_cfg"]) - P * float(r["t_cfg"])) / (float(r["e_base"]) - P * float(r["t_base"])))
    return {k: np.array(v) for k, v in R.items()}
def classify(R):
    out = {}
    for c in R:
        if len(c) <= 2: continue
        d = np.median(R[c]) - 1 - sum(np.median(R[p]) - 1 for p in dec(c)); bs = np.zeros(B)
        for j, x in enumerate([c] + dec(c)):
            a = R[x]; m = np.median(a[rng.integers(0, len(a), (B, len(a)))], axis=1); bs += m if j == 0 else -(m - 1)
        bs -= 1; se = bs.std(ddof=1); lo, hi = np.quantile(bs, [A / 2, 1 - A / 2])
        out[c] = ("*" if abs(d) > Z * se and (lo > 0 or hi < 0) else ("dag" if abs(d) > Z * se else ""), 100 * d)
    return out
md.append(f"## R7-1 — Puissance au repos sur M2 (médiane {idle_m2:.2f} W)\n")
V["idle_m2"] = idle_m2; V["acc_m2"] = {}
for reg, f in (("CPU", "M2_results_20261019/M2_repl_cpu_time.csv"), ("MEM", "M2_results_20261019/M2_repl_mem_time.csv")):
    rows = list(csv.DictReader(open(os.path.join(D, f))))
    share = st.median(idle_m2 * float(r["t_base"]) / float(r["e_base"]) for r in rows)
    a, b = classify(load(f, 0.0)), classify(load(f, idle_m2))
    cnt = lambda C: (sum(1 for s, d in C.values() if s == "*" and d > 0), sum(1 for s, d in C.values() if s == "*" and d < 0))
    lost = sorted(c for c in a if a[c][0] == "*" and b[c][0] != "*")
    two = [c for c in a if sum(p in ("Fa", "Bu", "Ob", "Me") for p in dec(c)) >= 2]
    keep2 = all(b[c][0] == "*" and b[c][1] > 0 for c in two)
    V["acc_m2"][reg] = dict(share=share, none=cnt(a), idle=cnt(b), lost=lost, keep_two=keep2)
    md.append(f"- {reg} : part de la baseline {100*share:.0f} % ; super/sub * {cnt(a)} → {cnt(b)} ; perdues : {', '.join(lost) or 'aucune'} ; ≥ 2 allouants toutes conservées : {keep2}")

# R7-3 ----------------------------------------------------------------------------------
V5 = json.load(open(os.path.join(OUT, "values.json")))
M = {"FaBuMe": 3, "BuObMe": 3, "BuMe": 2, "ObMe": 2}
ipc = [V5["decomp"][f"{k}_{c}"]["dinstr"] / (m * (1 + 2 / 1024)) for k in ("M1CPU", "M1MEM", "M2CPU", "M2MEM") for c, m in M.items()]
V["instr_per_call"] = (min(ipc), max(ipc))
md.append(f"\n## R7-3 — Surplus d'instructions par appel : {min(ipc):.1f} à {max(ipc):.1f} (4 compositions × 4 cellules)")

# R7-5 ----------------------------------------------------------------------------------
R = [r for r in csv.DictReader(open(os.path.join(D, "phaseB/B3_perf.csv"))) if r["dup"] == "1"]
def surplus(b, c):
    g = lambda x: st.median(float(r["instructions"]) for r in R if r["binary"] == b and r["config"] == x) / ((float(R[0]["K"]) + float(R[0]["warmup"])) * 200000)
    return g(c) - g("base") - sum(g(p) - g("base") for p in dec(c))
V["ctl_pgo"] = surplus("tiered", "StDeAd"); V["ctl_tc0"] = surplus("default", "StDeAd")
md.append(f"\n## R7-5 — Témoin, surplus d'instructions : TC = 0 {V['ctl_tc0']:+.1f} ; configuration par défaut {V['ctl_pgo']:+.1f}")

# R7-6 ----------------------------------------------------------------------------------
def abs_int(f, flt, c="FaBuMe"):
    E = {}; eb = []
    for r in csv.DictReader(open(os.path.join(D, f))):
        if flt(r): E.setdefault(r["config"], []).append(float(r["e_cfg"]) / float(r["e_base"])); eb.append(float(r["e_base"]))
    d = st.median(E[c]) - 1 - sum(st.median(E[p]) - 1 for p in dec(c))
    return d * st.median(eb) / (1000 * 200000) * 1e9
V["ab_abs"] = {}
for mach, f in (("M1", "M1_code_ab_20261020.csv"), ("M2", "M2b_results_20261020/M2b_code_ab.csv")):
    cpu = abs_int(f, lambda r: r["version"] == "new" and r["regime"] == "cpu"); mem = abs_int(f, lambda r: r["version"] == "new" and r["regime"] == "mem")
    V["ab_abs"][mach] = (cpu, mem, cpu / mem)
    md.append(f"- {mach} (A/B, code actuel) : FaBuMe {cpu:+.1f} nJ en calcul, {mem:+.1f} nJ en mémoire, rapport {cpu/mem:.2f}")
json.dump(V, open(os.path.join(OUT, "values_rev7.json"), "w"), indent=1, default=float)
open(os.path.join(HERE, "phaseR", "RESULTATS_REV7.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md))
