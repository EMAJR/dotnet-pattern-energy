# =====================================================================================
# Revision 6 -- calculations requested by the referee report on revision 5 (no new measurement).
#   R6-1  energy and time per call at the shared interface site (nJ and ns per call), with 95% CI
#   R6-2  pooling restricted to campaigns that ran the identical binary (topology campaigns out)
#   R6-3  decomposition: 95% CI on Delta E_int and on its terms; work valued at three references
#         (baseline = main, configuration = end point, Shapley midpoint); dilution factors with CI
#   R6-4  topology contrast in instructions, time and energy, four campaigns
# Output: rev5/values_rev6.json and phaseR/RESULTATS_REV6.md
# Usage: python3 analyse_rev6.py
# =====================================================================================
import csv, os, json, math
import numpy as np
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data_campaigns")
OUT = os.path.join(HERE, "rev5"); NIT = 200000; S_INSTR = 0.49e9; B = 4000
rng = np.random.default_rng(23)
def dec(c): return [c[i:i + 2] for i in range(0, len(c), 2)]
def parts(c):
    if "x" in c: b, k = c.split("x"); return [b] * int(k)
    return dec(c)
def nj(J, K=1000): return J / (K * NIT) * 1e9
md = ["# Calculs de la révision 6 (réponse au rapport de relecture)\n", "Généré par `analyse_rev6.py`. Aucune nouvelle mesure. IC 95 % par bootstrap (B = 4000).\n"]
V = {}

# ------------------------------------------------------------------ data access
class Src:
    """config -> arrays of absolute energy E (J per K tasks) and time t (s); baseline arrays E0, t0."""
    def __init__(self, E, T, E0, T0, K=1000):
        self.E, self.T, self.E0, self.T0, self.K = E, T, E0, T0, K
    @staticmethod
    def paired(path, flt=lambda r: True, key=lambda r: r["config"]):
        E, T, e0, t0 = {}, {}, [], []
        for r in csv.DictReader(open(os.path.join(D, path))):
            if not flt(r): continue
            E.setdefault(key(r), []).append(float(r["e_cfg"]) / float(r["e_base"]))
            T.setdefault(key(r), []).append(float(r["t_cfg"]) / float(r["t_base"]))
            e0.append(float(r["e_base"])); t0.append(float(r["t_base"]))
        mE, mT = st.median(e0), st.median(t0)
        return Src({c: np.array(v) * mE for c, v in E.items()}, {c: np.array(v) * mT for c, v in T.items()}, np.array(e0), np.array(t0))
    @staticmethod
    def absolute(path, flt):
        E, T = {}, {}
        R = [r for r in csv.DictReader(open(os.path.join(D, path))) if flt(r)]
        for r in R:
            E.setdefault(r["config"], []).append(float(r["energy_J"])); T.setdefault(r["config"], []).append(float(r["time_s"]))
        K = float(R[0]["K"])
        return Src({c: np.array(v) for c, v in E.items() if c != "base"}, {c: np.array(v) for c, v in T.items() if c != "base"},
                   np.array(E["base"]), np.array(T["base"]), K)
    def draw(self, boot):
        """medians (point estimate) or one bootstrap draw."""
        f = (lambda a: float(np.median(a[rng.integers(0, len(a), len(a))]))) if boot else (lambda a: float(np.median(a)))
        return {c: (f(self.E[c]), f(self.T[c])) for c in self.E}, f(self.E0), f(self.T0)

def instr_perf(path, flt, K, W, cfgs):
    R = [r for r in csv.DictReader(open(os.path.join(D, path))) if flt(r)]
    return {c: (st.median(float(r["instructions"]) for r in R if r["config"] == c) - S_INSTR) / ((K + W) * NIT) for c in cfgs}
KD = {"M1": "kdiag_machine1", "M2": "kdiag_machine2"}
def kd(m, ver, reg, cfgs):
    R = list(csv.DictReader(open(os.path.join(D, "kdiag_20261020", KD[m], "kdiag_perf.csv"))))
    return {c: (st.median(float(r["instructions"]) for r in R if r["version"] == ver and r["regime"] == reg and r["config"] == c) - S_INSTR) / (600 * NIT) for c in cfgs}

# ------------------------------------------------------------------ decomposition with three valuations
def L(a, b): return a if abs(a - b) < 1e-15 else (a - b) / (math.log(a) - math.log(b))
def decomp(X, E0, t0, ins, c):
    """X: cfg -> (E, t). Returns dict of interaction terms (J per window)."""
    i0 = ins["base"]; e0 = E0 / i0; c0 = t0 / i0; P0 = E0 / t0; sgn = {c: 1.0}
    for p in parts(c): sgn[p] = sgn.get(p, 0.0) - 1.0
    tot = sum(s * (X[x][0] - E0) for x, s in sgn.items())
    dI = sum(s * (ins[x] - i0) for x, s in sgn.items())
    w_base = e0 * dI
    w_conf = sum(s * (ins[x] - i0) * (X[x][0] / ins[x]) for x, s in sgn.items())
    w_shap = sum(s * (ins[x] - i0) * 0.5 * (e0 + X[x][0] / ins[x]) for x, s in sgn.items())
    tm = pw = 0.0
    for x, s in sgn.items():
        E, t = X[x]; e = E / ins[x]; Le = L(e, e0)
        tm += s * ins[x] * Le * math.log((t / ins[x]) / c0); pw += s * ins[x] * Le * math.log((E / t) / P0)
    return dict(tot=tot, w_base=w_base, w_conf=w_conf, w_shap=w_shap, time=tm, power=pw, dI=dI)
def decomp_ci(src, ins, c):
    X, E0, t0 = src.draw(False); pt = decomp(X, E0, t0, ins, c)
    bs = []
    for _ in range(B):
        Xb, E0b, t0b = src.draw(True); bs.append(decomp(Xb, E0b, t0b, ins, c))
    out = {}
    for k in pt:
        a = np.array([b[k] for b in bs]); lo, hi = np.quantile(a, [.025, .975])
        sc = (lambda v: v) if k == "dI" else (lambda v: nj(v, src.K))
        out[k] = (sc(pt[k]), sc(lo), sc(hi))
    out["E0"] = nj(E0, src.K); out["delta"] = 100 * pt["tot"] / E0
    out["_boot_tot"] = [nj(b["tot"], src.K) for b in bs]
    return out
C13 = ["base", "St", "De", "Ad", "Fa", "Bu", "Ob", "Me", "FaBuMe", "BuObMe", "BuMe", "ObMe", "StDeAd"]
CELLSRC = {"M1CPU": (Src.paired("M1_cpu_ET.csv"), instr_perf("M1_perf_cpu.csv", lambda r: True, 5000, 100, C13)),
           "M1MEM": (Src.paired("M1_mem_ET.csv"), kd("M1", "new", "mem", C13)),
           "M2CPU": (Src.paired("M2_results_20261019/M2_repl_cpu_time.csv"), kd("M2", "new", "cpu", C13)),
           "M2MEM": (Src.paired("M2_results_20261019/M2_repl_mem_time.csv"), kd("M2", "new", "mem", C13))}
M_LAYERS = {"FaBuMe": 3, "BuObMe": 3, "BuMe": 2, "ObMe": 2}

# R6-1: per call ------------------------------------------------------------------------------
md.append("## R6-1 — Énergie et temps par appel au site partagé\n")
md.append("Appels au site partagé par itération = m (un `Step` par couche), plus 2m/1024 appels de bloc. Interaction divisée par m(1 + 2/1024).\n")
md.append("| cellule | comp. | ΔE_int (nJ/itér.) [IC] | nJ par appel [IC] | ns par appel (temps) |"); md.append("|---|---|---|---|---|")
V["percall"] = {}
for k, (src, ins) in CELLSRC.items():
    X, E0, t0 = src.draw(False)
    for c, m in M_LAYERS.items():
        r = decomp_ci(src, ins, c); calls = m * (1 + 2 / 1024)
        tot = r["tot"]; pc = (tot[0] / calls, tot[1] / calls, tot[2] / calls)
        dt = X[c][1] - t0 - sum(X[p][1] - t0 for p in parts(c)); ns = dt / (src.K * NIT) * 1e9 / calls
        V["percall"][f"{k}_{c}"] = dict(tot=tot, pc=pc, ns=ns)
        md.append(f"| {k} | {c} | {tot[0]:+.1f} [{tot[1]:+.1f} ; {tot[2]:+.1f}] | {pc[0]:+.1f} [{pc[1]:+.1f} ; {pc[2]:+.1f}] | {ns:+.2f} |")
pcs = [v["pc"][0] for k, v in V["percall"].items() if "CPU" in k]
V["percall_cpu_range"] = (min(pcs), max(pcs))
nss = [v["ns"] for k, v in V["percall"].items() if "CPU" in k]; V["ns_cpu_range"] = (min(nss), max(nss))

# R6-3b: dilution factors with CI -------------------------------------------------------------
md.append("\n## R6-3b — Facteurs de dilution (ΔE_int calcul / ΔE_int mémoire), FaBuMe\n")
V["dil"] = {}
for mach in ("M1", "M2"):
    a = decomp_ci(*CELLSRC[mach + "CPU"], "FaBuMe"); b = decomp_ci(*CELLSRC[mach + "MEM"], "FaBuMe")
    ra = np.array(a["_boot_tot"]) / np.array(b["_boot_tot"]); lo, hi = np.quantile(ra, [.025, .975])
    V["dil"][mach] = (a["tot"][0] / b["tot"][0], lo, hi)
    md.append(f"- {mach} : {a['tot'][0]/b['tot'][0]:.2f} [{lo:.2f} ; {hi:.2f}] (ΔE_int {a['tot'][0]:+.1f} contre {b['tot'][0]:+.1f} nJ)")

# R6-3: cases with CI and three valuations ----------------------------------------------------
md.append("\n## R6-3 — Décomposition : IC et trois valorisations du travail\n")
md.append("| cas | ΔE_int [IC] | travail, réf. baseline [IC] | travail, réf. configuration | travail, Shapley | temps / instr. [IC] | puissance [IC] |")
md.append("|---|---|---|---|---|---|---|")
CASES = []
def add(label, tag, src, ins, c):
    r = decomp_ci(src, ins, c); r.pop("_boot_tot"); r.update(label=label, tag=tag); CASES.append(r)
    f = lambda t: f"{t[0]:+.1f} [{t[1]:+.1f} ; {t[2]:+.1f}]"
    md.append(f"| {label} | {f(r['tot'])} | {f(r['w_base'])} | {r['w_conf'][0]:+.1f} | {r['w_shap'][0]:+.1f} | {f(r['time'])} | {f(r['power'])} |")
add("Regime, M1 CPU", "DilCpu", *CELLSRC["M1CPU"], "FaBuMe")
add("Regime, M1 MEM", "DilMem", *CELLSRC["M1MEM"], "FaBuMe")
for ver, tag in (("old", "KerPrev"), ("new", "KerCur")):
    add(f"Kernel {ver}", tag, Src.paired("M1_code_ab_20261020.csv", lambda r, v=ver: r["version"] == v and r["regime"] == "cpu"), kd("M1", ver, "cpu", C13), "FaBuMe")
for topo, tag in (("0", "TopoShared"), ("1", "TopoDed")):
    add(f"Topology M2 topo{topo}", tag, Src.paired("M2_results_20261019/M2_B4_energy.csv", lambda r, t=topo: r["topo"] == t),
        instr_perf("M2_results_20261019/M2_B4_perf.csv", lambda r, t=topo: r["topo"] == t, 2000, 100, ["base", "Fa", "Bu", "Me", "FaBuMe"]), "FaBuMe")
w8 = Src.absolute("phaseB/B1_perf_weights.csv", lambda r: r["weight"] == "8")
R8 = [r for r in csv.DictReader(open(os.path.join(D, "phaseB/B1_perf_weights.csv"))) if r["weight"] == "8"]
ins8 = {c: (st.median(float(r["instructions"]) for r in R8 if r["config"] == c) - S_INSTR) / ((float(R8[0]["K"]) + 100) * NIT) for c in C13}
add("Weight w=8 FaBuMe", "WtEight", w8, ins8, "FaBuMe"); add("Weight w=8 control", "WtEightCtl", w8, ins8, "StDeAd")
dsrc = Src.paired("M1_dispatch_energy_v2.csv", lambda r: r["dup"] in ("1", "3"), key=lambda r: r["config"] if r["dup"] == "1" else r["config"] + "x" + r["dup"])
Rp = list(csv.DictReader(open(os.path.join(D, "M1_dispatch_perf_v2.csv"))))
gi = lambda c, d: (st.median(float(r["instructions"]) for r in Rp if r["config"] == c and r["dup"] == d) - S_INSTR) / (5100 * NIT)
dins = {"base": gi("base", "1"), "Bu": gi("Bu", "1"), "Bux3": gi("Bu", "3"), "BuMe": gi("BuMe", "1"), "Me": gi("Me", "1")}
add("Bu x3", "DupBux", dsrc, dins, "Bux3"); add("BuMe (dispatch)", "DupBuMe", dsrc, dins, "BuMe")
for b, tag in (("default", "JitMeasured"), ("tiered", "JitDefault")):
    add(f"JIT {tag}", tag, Src.paired("phaseB/B3_energy.csv", lambda r, bb=b: r["binary"] == bb and r["dup"] == "1"),
        instr_perf("phaseB/B3_perf.csv", lambda r, bb=b: r["binary"] == bb and r["dup"] == "1", 3000, 400, ["base", "Fa", "Bu", "Me", "FaBuMe"]), "FaBuMe")
V["cases"] = CASES

# R6-2: pooling on the identical binary --------------------------------------------------------
def pool(vv):
    k = len(vv); w = [1 / s ** 2 for _, s in vv]; fe = sum(a * d for a, (d, _) in zip(w, vv)) / sum(w)
    Q = sum(a * (d - fe) ** 2 for a, (d, _) in zip(w, vv)); C = sum(w) - sum(a * a for a in w) / sum(w)
    t2 = max(0.0, (Q - (k - 1)) / C); t2r = t2
    for _ in range(1000):
        wr = [1 / (s ** 2 + t2r) for _, s in vv]; m_ = sum(a * d for a, (d, _) in zip(wr, vv)) / sum(wr)
        new = max(0.0, sum(a * a * ((d - m_) ** 2 - s ** 2) for a, (d, s) in zip(wr, vv)) / sum(a * a for a in wr) + 1 / sum(wr))
        if abs(new - t2r) < 1e-14: break
        t2r = new
    wr = [1 / (s ** 2 + t2r) for _, s in vv]; mur = sum(a * d for a, (d, _) in zip(wr, vv)) / sum(wr)
    # modified Knapp-Hartung (Roever, Knapp & Friede 2015): q is floored at 1 so the interval is never
    # narrower than the one obtained with the REML weights alone
    qhk = sum(a * (d - mur) ** 2 for a, (d, _) in zip(wr, vv)) / (k - 1)
    hk = math.sqrt(max(1.0, qhk) / sum(wr))
    tq = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365}[k - 1]
    return dict(k=k, Q=Q, reml=mur, lo=mur - tq * hk, hi=mur + tq * hk, tau=math.sqrt(t2r))
def d_se(path, flt, c):
    E = {}
    for r in csv.DictReader(open(os.path.join(D, path))):
        if flt(r): E.setdefault(r["config"], []).append(float(r["e_cfg"]) / float(r["e_base"]))
    E = {k: np.array(v) for k, v in E.items()}
    d = float(np.median(E[c])) - 1 - sum(float(np.median(E[p])) - 1 for p in dec(c))
    bs = np.zeros(B) + 0.0
    for j, x in enumerate([c] + dec(c)):
        a = E[x]; med = np.median(a[rng.integers(0, len(a), (B, len(a)))], axis=1)
        bs += med if j == 0 else -(med - 1)
    return d, float((bs - 1).std(ddof=1))
SAME = {"M1": [("M1_cpu_ET.csv", lambda r: True), ("M1_code_ab_20261020.csv", lambda r: r["version"] == "new" and r["regime"] == "cpu"),
               ("M1_dispatch_energy_v2.csv", lambda r: r["dup"] == "1"), ("M1_sweep_cpu.csv", lambda r: r["kernel_rep"] == "1"),
               ("M1_sweep_cpu_v2.csv", lambda r: r["kernel_rep"] == "1"), ("M1_amp_cpu_1x.csv", lambda r: True)],
        "M2": [("M2_results_20261019/M2_repl_cpu_time.csv", lambda r: True), ("M2b_results_20261020/M2b_code_ab.csv", lambda r: r["version"] == "new" and r["regime"] == "cpu")]}
md.append("\n## R6-2 — Regroupement limité aux campagnes au binaire identique (sans les deux campagnes de topologie)\n")
V["pool_same"] = {}
for mach, L_ in SAME.items():
    vv = [d_se(p, f, "FaBuMe") for p, f in L_]
    P = pool(vv); V["pool_same"][mach] = P
    md.append(f"- {mach} FaBuMe : k = {P['k']}, REML + HK {100*P['reml']:+.1f} [{100*P['lo']:+.1f} ; {100*P['hi']:+.1f}], τ̂ = {100*P['tau']:.1f}, Q = {P['Q']:.1f}")

# R6-4: topology contrast in instructions, time and energy -------------------------------------
md.append("\n## R6-4 — Contraste partagé − dédié en instructions, temps et énergie (FaBuMe, BuMe)\n")
md.append("| campagne | comp. | Δ instr. partagé / dédié | contraste temps (pts) | contraste énergie (pts) |"); md.append("|---|---|---|---|---|")
V["topo_time"] = {}
for lab, fe, fp in [("M1 #1", "phaseB/B4_energy.csv", "phaseB/B4_perf.csv"), ("M1 #2", "phaseB/B4_energy_rep2.csv", "phaseB/B4_perf_rep2.csv"),
                    ("M2 #1", "M2_results_20261019/M2_B4_energy.csv", "M2_results_20261019/M2_B4_perf.csv"),
                    ("M2 #2", "M2b_results_20261020/M2b_B4_energy.csv", "M2b_results_20261020/M2b_B4_perf.csv")]:
    for c in ("FaBuMe", "BuMe", "ObMe", "FaBu", "BuOb", "BuObMe"):
        out = {}
        for t in "01":
            s = Src.paired(fe, lambda r, tt=t: r["topo"] == tt); X, E0, t0 = s.draw(False)
            out[t] = (100 * (X[c][0] - E0 - sum(X[p][0] - E0 for p in dec(c))) / E0, 100 * (X[c][1] - t0 - sum(X[p][1] - t0 for p in dec(c))) / t0)
        V["topo_time"][f"{lab}_{c}"] = dict(e=out["0"][0] - out["1"][0], t=out["0"][1] - out["1"][1])
        if c in ("FaBuMe", "BuMe"):
            md.append(f"| {lab} | {c} | — | {out['0'][1]-out['1'][1]:+.1f} | {out['0'][0]-out['1'][0]:+.1f} |")
tt = [v["t"] for v in V["topo_time"].values()]; ee = [v["e"] for v in V["topo_time"].values()]
V["topo_time_range"] = (min(tt), max(tt)); V["topo_energy_range"] = (min(ee), max(ee))
md.append(f"\nContraste en temps, toutes compositions allouantes et campagnes : {min(tt):+.0f} à {max(tt):+.0f} points ; en énergie : {min(ee):+.0f} à {max(ee):+.0f}.")

json.dump(V, open(os.path.join(OUT, "values_rev6.json"), "w"), indent=1, default=float)
open(os.path.join(HERE, "phaseR", "RESULTATS_REV6.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md))
