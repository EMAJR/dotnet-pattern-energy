# =====================================================================================
# Revision 5 -- every number of the article recomputed on the CURRENT kernel code.
# No new measurement. Inputs: data_campaigns/. Outputs: rev5/ (values.json, numbers.tex,
# tab_*.tex, fig_*_v4.pdf) and phaseR/RESULTATS_NOYAU_ACTUEL.md.
#
#   M1  four current-kernel matrices (M1 ET, M2 19/10): delta, 2SE, * / dagger, pass bootstrap
#   M2  changes of sign / star versus the September matrices (previous kernel)
#   M3  pooling over current-kernel campaigns (REML + Hartung-Knapp, DL, Q, I2, leave-one-out)
#   M4  kernel-code sensitivity table (A/B, same evening, both machines)
#   M5  LMDI decomposition of the interaction: work x cost per instruction x power
#   M6  isolated signatures, dose-response, allocation correlations, figures
# Usage: python3 analyse_rev5_main.py
# =====================================================================================
import csv, os, json, math
import numpy as np
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data_campaigns"); OUT = os.path.join(HERE, "rev5"); os.makedirs(OUT, exist_ok=True)
PAT = ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]; ALLOC = {"Fa", "Bu", "Ob", "Me"}; INDIR = {"St", "De", "Ad"}
Z = 3.0976; ALPHA = 0.05 / 26; NIT = 200000
S_INSTR = 0.49e9            # process start-up instructions (K = 5000 vs K = 500, both machines)
B_MAIN = 20000
V = {}                       # every value used by the article
def dec(c): return [c[i:i + 2] for i in range(0, len(c), 2)]
def parts(c):
    if "x" in c: b, k = c.split("x"); return [b] * int(k)
    return dec(c)
def nalloc(c): return sum(p in ALLOC for p in dec(c))

# ------------------------------------------------------------------ loading
class Mat:
    """config -> {rep: (e_ratio, t_ratio)}; baseline medians E0 (J per window), t0 (s)."""
    def __init__(self, path, flt=lambda r: True, key=lambda r: r["config"]):
        self.v = {}; eb = []; tb = []
        for r in csv.DictReader(open(path)):
            if not flt(r): continue
            e = float(r["e_cfg"]) / float(r["e_base"])
            t = float(r["t_cfg"]) / float(r["t_base"]) if r.get("t_cfg") not in (None, "") else float("nan")
            self.v.setdefault(key(r), {})[r["rep"] + "_" + str(len(self.v.get(key(r), {})))] = (e, t)
            eb.append(float(r["e_base"]))
            if r.get("t_base") not in (None, ""): tb.append(float(r["t_base"]))
        # re-key by plain rep number (one value per rep and config in every file used here)
        self.v = {c: {k.split("_")[0]: x for k, x in d.items()} for c, d in self.v.items()}
        self.E0 = st.median(eb); self.t0 = st.median(tb) if tb else float("nan")
    def arr(self, c, i=0): return np.array([x[i] for x in self.v[c].values()])
    def rho(self, c, i=0): return float(np.median(self.arr(c, i)))
    def has(self, c): return c in self.v and all(p in self.v for p in parts(c))
    def delta(self, c, i=0): return self.rho(c, i) - 1 - sum(self.rho(p, i) - 1 for p in parts(c))

rng = np.random.default_rng(11)
def boot_indep(M, c, B, i=0):
    out = np.zeros(B) - 1.0
    for k, cfg in enumerate([c] + parts(c)):
        a = M.arr(cfg, i); idx = rng.integers(0, len(a), (B, len(a))); med = np.median(a[idx], axis=1)
        out += (med if k == 0 else -(med - 1))
    return out
def boot_pass(M, c, B, i=0):
    cfgs = [c] + parts(c); reps = sorted(set.intersection(*[set(M.v[x]) for x in cfgs]))
    A = np.array([[M.v[x][r][i] for r in reps] for x in cfgs])          # cfg x rep
    idx = rng.integers(0, len(reps), (B, len(reps))); med = np.median(A[:, idx], axis=2)   # cfg x B
    return med[0] - 1 - (med[1:] - 1).sum(axis=0)
def sig(M, c, B=B_MAIN, i=0):
    d = M.delta(c, i); bs = boot_indep(M, c, B, i); se = float(bs.std(ddof=1))
    lo, hi = np.quantile(bs, [ALPHA / 2, 1 - ALPHA / 2])
    z = abs(d) > Z * se; p = lo > 0 or hi < 0
    return dict(d=100 * d, se=100 * se, two=200 * se, star="*" if z and p else ("dag" if z else ""), z=d / se if se else 0)

def fmt(x, nd=1, sign=True): return (f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}").replace("-", "-")
def tex_d(s, nd=1):
    m = {"*": "^{\\ast}", "dag": "^{\\dagger}", "": ""}[s["star"]]
    return f"${fmt(s['d'], nd)}{m}$ {{\\scriptsize[{s['two']:.1f}]}}"

CELLS = {"M1CPU": ("M1_cpu_ET.csv", "M1", "CPU"), "M1MEM": ("M1_mem_ET.csv", "M1", "MEM"),
         "M2CPU": ("M2_results_20261019/M2_repl_cpu_time.csv", "M2", "CPU"),
         "M2MEM": ("M2_results_20261019/M2_repl_mem_time.csv", "M2", "MEM")}
OLD = {"M1CPU": "M1_cpu.csv", "M1MEM": "M1_mem.csv", "M2CPU": "M2_cpu.csv", "M2MEM": "M2_mem.csv"}
MAT = {k: Mat(os.path.join(D, f)) for k, (f, _, _) in CELLS.items()}
MOLD = {k: Mat(os.path.join(D, f)) for k, f in OLD.items()}
COMPS = sorted([c for c in MAT["M1CPU"].v if len(dec(c)) >= 2], key=lambda c: (-nalloc(c), c))
SIG = {k: {c: sig(M, c) for c in COMPS} for k, M in MAT.items()}
SIGOLD = {k: {c: sig(M, c, 5000) for c in COMPS} for k, M in MOLD.items()}
md = ["# Résultats sur le code actuel du noyau (révision 5)\n", "Généré par `analyse_rev5_main.py`. Aucune nouvelle mesure.\n"]

# ------------------------------------------------------------------ M1: matrices
md.append("## 1. Matrices du code actuel (M1 ET, M2 19/10), B = 20 000\n")
md.append("| cellule | E₀ (J / 1000 tâches) | t₀ (s) | * super | * sub | † | rapport SE passes / indép. (médiane) |")
md.append("|---|---|---|---|---|---|---|")
for k, M in MAT.items():
    S = SIG[k]
    nsup = sum(1 for c in COMPS if S[c]["star"] == "*" and S[c]["d"] > 0); nsub = sum(1 for c in COMPS if S[c]["star"] == "*" and S[c]["d"] < 0)
    ndag = sum(1 for c in COMPS if S[c]["star"] == "dag")
    ratio = st.median(float(boot_pass(M, c, 3000).std(ddof=1)) / (S[c]["se"] / 100) for c in COMPS)
    # pass-bootstrap classification change under the z-rule
    chg = [c for c in COMPS if (abs(S[c]["d"]) > Z * 100 * float(boot_pass(M, c, 3000).std(ddof=1))) != (abs(S[c]["d"]) > Z * S[c]["se"])]
    V[k] = dict(E0=M.E0, t0=M.t0, nsup=nsup, nsub=nsub, ndag=ndag, passratio=ratio, passchg=chg,
                sub=[c for c in COMPS if S[c]["star"] == "*" and S[c]["d"] < 0])
    md.append(f"| {k} | {M.E0:.2f} | {M.t0:.3f} | {nsup} | {nsub} | {ndag} | {ratio:.2f} (changements z : {', '.join(chg) or 'aucun'}) |")
allsub = [c for k in MAT for c in V[k]["sub"]]
V["sub_all_indirection"] = all(any(p in INDIR for p in dec(c)) for c in allsub)
V["comps_without_indirection"] = [c for c in COMPS if not any(p in INDIR for p in dec(c))]
md.append(f"\nSous-additives * : {len(allsub)} au total ; toutes avec un patron d'indirection : {V['sub_all_indirection']}. "
          f"Compositions sans indirection : {', '.join(V['comps_without_indirection'])} (toutes ≥ 2 allouants).\n")

# ------------------------------------------------------------------ M2: changes vs previous kernel
md.append("## 2. Changements de signe ou d'étoile : septembre (ancien noyau) → code actuel\n")
md.append("| cellule | composition | septembre | actuel |"); md.append("|---|---|---|---|")
chg_rows = []
for k in MAT:
    for c in COMPS:
        a, b = SIGOLD[k][c], SIG[k][c]
        if a["star"] != b["star"] or (a["star"] and b["star"] and np.sign(a["d"]) != np.sign(b["d"])):
            chg_rows.append([k, c, f"{a['d']:+.1f}{a['star']}", f"{b['d']:+.1f}{b['star']}"])
            md.append(f"| {k} | {c} | {a['d']:+.1f}{a['star'].replace('dag','†')} | {b['d']:+.1f}{b['star'].replace('dag','†')} |")
with open(os.path.join(OUT, "R5_changements.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["cell", "comp", "september", "current"]); w.writerows(chg_rows)

# ------------------------------------------------------------------ M3: pooling
def pool(vv):
    k = len(vv); w = [1 / s ** 2 for _, s in vv]; fe = sum(a * d for a, (d, _) in zip(w, vv)) / sum(w)
    Q = sum(a * (d - fe) ** 2 for a, (d, _) in zip(w, vv)); C = sum(w) - sum(a * a for a in w) / sum(w)
    t2 = max(0.0, (Q - (k - 1)) / C); wd = [1 / (s ** 2 + t2) for _, s in vv]
    mu = sum(a * d for a, (d, _) in zip(wd, vv)) / sum(wd); se = math.sqrt(1 / sum(wd))
    t2r = t2
    for _ in range(1000):
        wr = [1 / (s ** 2 + t2r) for _, s in vv]; m = sum(a * d for a, (d, _) in zip(wr, vv)) / sum(wr)
        new = max(0.0, sum(a * a * ((d - m) ** 2 - s ** 2) for a, (d, s) in zip(wr, vv)) / sum(a * a for a in wr) + 1 / sum(wr))
        if abs(new - t2r) < 1e-14: break
        t2r = new
    wr = [1 / (s ** 2 + t2r) for _, s in vv]; mur = sum(a * d for a, (d, _) in zip(wr, vv)) / sum(wr)
    # modified Knapp-Hartung (Roever, Knapp & Friede 2015): q is floored at 1 so the interval is never
    # narrower than the one obtained with the REML weights alone
    qhk = sum(a * (d - mur) ** 2 for a, (d, _) in zip(wr, vv)) / (k - 1)
    hk = math.sqrt(max(1.0, qhk) / sum(wr))
    tq = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306}[k - 1]
    I2 = max(0.0, (Q - (k - 1)) / Q) if Q > 0 else 0.0
    from math import gamma
    def chi2sf(x, df):           # numerical upper tail
        a = df / 2; n = 20000; top = x / 2 + 60; h = (top - x / 2) / n
        return sum(((x / 2 + (j + .5) * h) ** (a - 1)) * math.exp(-(x / 2 + (j + .5) * h)) for j in range(n)) * h / gamma(a)
    return dict(k=k, Q=Q, p=chi2sf(Q, k - 1) if Q > 0 else 1.0, I2=I2, dl=mu, dlse=se, tau_dl=math.sqrt(t2),
                reml=mur, lo=mur - tq * hk, hi=mur + tq * hk, tau=math.sqrt(t2r))
CAMP = {
 "M1": [("ET matrix", "M1_cpu_ET.csv", lambda r: True),
        ("code A/B, current", "M1_code_ab_20261020.csv", lambda r: r["version"] == "new" and r["regime"] == "cpu"),
        ("dispatch 1", "M1_dispatch_energy.csv", lambda r: r["dup"] == "1"),
        ("dispatch 2", "M1_dispatch_energy_v2.csv", lambda r: r["dup"] == "1"),
        ("topology 1, shared", "phaseB/B4_energy.csv", lambda r: r["topo"] == "0"),
        ("topology 2, shared", "phaseB/B4_energy_rep2.csv", lambda r: r["topo"] == "0"),
        ("weight sweep 1, w=1", "M1_sweep_cpu.csv", lambda r: r["kernel_rep"] == "1"),
        ("weight sweep 2, w=1", "M1_sweep_cpu_v2.csv", lambda r: r["kernel_rep"] == "1"),
        ("amplification, 1x", "M1_amp_cpu_1x.csv", lambda r: True)],
 "M2": [("19/10 matrix", "M2_results_20261019/M2_repl_cpu_time.csv", lambda r: True),
        ("code A/B, current", "M2b_results_20261020/M2b_code_ab.csv", lambda r: r["version"] == "new" and r["regime"] == "cpu"),
        ("topology 1, shared", "M2_results_20261019/M2_B4_energy.csv", lambda r: r["topo"] == "0"),
        ("topology 2, shared", "M2b_results_20261020/M2b_B4_energy.csv", lambda r: r["topo"] == "0")]}
POOLC = ["FaBuMe", "BuObMe", "BuMe", "ObMe", "StDeAd"]
CM = {m: [(lab, Mat(os.path.join(D, f), flt)) for lab, f, flt in L] for m, L in CAMP.items()}
md.append("\n## 3. Regroupement des campagnes du code actuel (calcul)\n")
md.append("| machine | comp. | k | valeurs | REML + HK [IC 95 %] | DL ± 2SE | τ̂ (REML) | Q (ddl), p | I² | retrait d'une campagne (REML) |")
md.append("|---|---|---|---|---|---|---|---|---|---|")
V["pool"] = {}
for m in CM:
    for c in POOLC:
        vv = [(lab, M.delta(c), float(boot_indep(M, c, 4000).std(ddof=1))) for lab, M in CM[m] if M.has(c)]
        if len(vv) < 2: continue
        P = pool([(d, s) for _, d, s in vv])
        loo = [pool([(d, s) for j, (_, d, s) in enumerate(vv) if j != i])["reml"] for i in range(len(vv))] if len(vv) > 2 else []
        P.update(values=[(l, 100 * d, 200 * s) for l, d, s in vv], loo_lo=min(loo) if loo else None, loo_hi=max(loo) if loo else None)
        V["pool"][f"{m}_{c}"] = P
        vals = ", ".join(f"{d:+.1f}" for _, d, _ in P["values"])
        md.append(f"| {m} | {c} | {P['k']} | {vals} | {100*P['reml']:+.1f} [{100*P['lo']:+.1f} ; {100*P['hi']:+.1f}] | "
                  f"{100*P['dl']:+.1f} ± {200*P['dlse']:.1f} | {100*P['tau']:.1f} | {P['Q']:.1f} ({P['k']-1}), {P['p']:.2f} | {100*P['I2']:.0f} % | "
                  + (f"{100*P['loo_lo']:+.1f} à {100*P['loo_hi']:+.1f}" if loo else "—") + " |")
# dispatch campaigns: same signature, energy shift
d1 = dict(CM["M1"])["dispatch 1"]; d2 = dict(CM["M1"])["dispatch 2"]
V["disp_shift"] = {c: (100 * d1.delta(c), 100 * d2.delta(c)) for c in ["BuMe", "ObMe", "StDeAd"] if d1.has(c) and d2.has(c)}

# ------------------------------------------------------------------ M4: kernel-code sensitivity
md.append("\n## 4. Sensibilité au code du noyau (A/B, même soirée)\n")
AB = {"M1": "M1_code_ab_20261020.csv", "M2": "M2b_results_20261020/M2b_code_ab.csv"}
KD = {"M1": "kdiag_machine1", "M2": "kdiag_machine2"}
def kd_instr(m, ver, reg, cfg):
    R = [r for r in csv.DictReader(open(os.path.join(D, "kdiag_20261020", KD[m], "kdiag_perf.csv")))
         if r["version"] == ver and r["regime"] == reg and r["config"] == cfg]
    return (st.median(float(r["instructions"]) for r in R) - S_INSTR) / (600 * NIT)
V["kernel"] = {}
md.append("| machine | régime | version | E₀ (J) | t₀ (s) | instr. noyau / itér. | FaBuMe | BuMe | BuObMe | StDeAd |")
md.append("|---|---|---|---|---|---|---|---|---|---|")
for m, f in AB.items():
    for reg in ("cpu", "mem"):
        row = {}
        for ver in ("old", "new"):
            M = Mat(os.path.join(D, f), lambda r, v=ver, g=reg: r["version"] == v and r["regime"] == g)
            row[ver] = dict(E0=M.E0, t0=M.t0, instr=kd_instr(m, ver, reg, "base"),
                            **{c: (100 * M.delta(c), 100 * float(boot_indep(M, c, 4000).std(ddof=1))) for c in ["FaBuMe", "BuMe", "BuObMe", "StDeAd"]})
        for c in ["FaBuMe", "BuMe", "BuObMe", "StDeAd"]:
            (a, sa), (b, sb) = row["old"][c], row["new"][c]; row[c + "_z"] = (b - a) / math.hypot(sa, sb)
        V["kernel"][f"{m}{reg.upper()}"] = row
        for ver in ("old", "new"):
            r = row[ver]
            md.append(f"| {m} | {reg} | {ver} | {r['E0']:.2f} | {r['t0']:.3f} | {r['instr']:.1f} | " +
                      " | ".join(f"{r[c][0]:+.1f}" for c in ["FaBuMe", "BuMe", "BuObMe", "StDeAd"]) + " |")
        md.append(f"| | | z(actuel − ancien) | | | | " + " | ".join(f"{row[c+'_z']:+.1f}" for c in ["FaBuMe", "BuMe", "BuObMe", "StDeAd"]) + " |")

# ------------------------------------------------------------------ M5: LMDI decomposition
def L(a, b): return a if abs(a - b) < 1e-15 else (a - b) / (math.log(a) - math.log(b))
def lmdi(E0, t0, i0, X):
    """Per configuration: energy per instruction e = c * P, with c = t / I and P = E / t.
    Returns (I, e, time-part, power-part) where e - e0 = L(e, e0)[ln(c/c0) + ln(P/P0)] (exact, 2 factors)."""
    e0 = E0 / i0; c0 = t0 / i0; P0 = E0 / t0; out = {}
    for c, (E, t, i) in X.items():
        e = E / i; cx = t / i; Px = E / t; Le = L(e, e0)
        out[c] = (i, e, Le * math.log(cx / c0), Le * math.log(Px / P0))
    return out
def interaction(c, X, PD, E0, i0=None):
    """Exact split: dE_int = e0 * dI_int (work valued at the baseline energy per instruction)
                           + sum_s sign_s * I_s * (e_s - e0)  (context), context = time part + power part."""
    i0 = PD["_i0"]; e0 = E0 / i0
    tot = X[c][0] - E0 - sum(X[p][0] - E0 for p in parts(c))
    dI = (PD[c][0] - i0) - sum(PD[p][0] - i0 for p in parts(c))
    tm = PD[c][0] * PD[c][2] - sum(PD[p][0] * PD[p][2] for p in parts(c))
    pw = PD[c][0] * PD[c][3] - sum(PD[p][0] * PD[p][3] for p in parts(c))
    work = e0 * dI
    assert abs(work + tm + pw - tot) < 1e-9 * max(1.0, abs(tot)), (c, work + tm + pw, tot)
    return tot, [work, tm, pw]
def nj(J, Ktasks=1000): return J / (Ktasks * NIT) * 1e9
def decomp_from_mat(M, instr, Ktasks=1000):
    """M: energy matrix (ratios); instr: cfg -> net instructions per iteration."""
    E0, t0 = M.E0, M.t0; X = {}
    for c in instr:
        if c == "base": continue
        X[c] = (M.rho(c, 0) * E0, M.rho(c, 1) * t0, instr[c])
    PD = lmdi(E0, t0, instr["base"], X); PD["_i0"] = instr["base"]
    return E0, X, PD
def instr_perf(path, flt, K, W, cfgs):
    R = [r for r in csv.DictReader(open(path)) if flt(r)]
    return {c: (st.median(float(r["instructions"]) for r in R if r["config"] == c) - S_INSTR) / ((K + W) * NIT) for c in cfgs}
C13 = ["base", "St", "De", "Ad", "Fa", "Bu", "Ob", "Me", "FaBuMe", "BuObMe", "BuMe", "ObMe", "StDeAd"]
INSTR = {"M1CPU": instr_perf(os.path.join(D, "M1_perf_cpu.csv"), lambda r: True, 5000, 100, C13),
         "M1MEM": {c: kd_instr("M1", "new", "mem", c) for c in C13},
         "M2CPU": {c: kd_instr("M2", "new", "cpu", c) for c in C13},
         "M2MEM": {c: kd_instr("M2", "new", "mem", c) for c in C13}}
md.append("\n## 5. Décomposition LMDI de l'interaction (nJ par itération)\n")
md.append("Travail = surplus d'instructions × énergie par instruction de la baseline ; coût = variation du temps par instruction ; puissance = variation de E / t (partage LMDI à 2 facteurs de l'énergie par instruction). Somme des trois = ΔE_int exactement.\n")
md.append("| cellule | comp. | δ (pts) | E₀ (nJ/itér.) | ΔE_int | travail | coût / instr. | puissance | Δ instr. / itér. |")
md.append("|---|---|---|---|---|---|---|---|---|")
V["decomp"] = {}
for k in MAT:
    E0, X, PD = decomp_from_mat(MAT[k], INSTR[k])
    for c in ["FaBuMe", "BuObMe", "BuMe", "ObMe", "StDeAd"]:
        tot, w = interaction(c, X, PD, E0)
        di = INSTR[k][c] - INSTR[k]["base"] - sum(INSTR[k][p] - INSTR[k]["base"] for p in parts(c))
        V["decomp"][f"{k}_{c}"] = dict(delta=100 * tot / E0, E0=nj(E0), tot=nj(tot), work=nj(w[0]), cost=nj(w[1]), power=nj(w[2]), dinstr=di)
        md.append(f"| {k} | {c} | {100*tot/E0:+.1f} | {nj(E0):.1f} | {nj(tot):+.1f} | {nj(w[0]):+.1f} | {nj(w[1]):+.1f} | {nj(w[2]):+.1f} | {di:+.1f} |")

# five cases
md.append("\n### Les cinq cas « même travail, coût différent »\n")
md.append("| cas | configuration | δ (pts) | E₀ (nJ/itér.) | ΔE_int | travail | coût / instr. | puissance | Δ instr. / itér. |")
md.append("|---|---|---|---|---|---|---|---|---|")
CASES = []
def case(label, conf, E0, X, PD, instr, c, Ktasks):
    tot, w = interaction(c, X, PD, E0)
    di = instr[c] - instr["base"] - sum(instr[p] - instr["base"] for p in parts(c))
    row = dict(case=label, conf=conf, delta=100 * tot / E0, E0=nj(E0, Ktasks), tot=nj(tot, Ktasks), work=nj(w[0], Ktasks),
               cost=nj(w[1], Ktasks), power=nj(w[2], Ktasks), dinstr=di)
    CASES.append(row)
    md.append(f"| {label} | {conf} | {row['delta']:+.1f} | {row['E0']:.1f} | {row['tot']:+.1f} | {row['work']:+.1f} | {row['cost']:+.1f} | {row['power']:+.1f} | {di:+.1f} |")
# (1) dilution: from the cells
for k, lab in (("M1CPU", "M1, $W_{\\mathrm{CPU}}$"), ("M1MEM", "M1, $W_{\\mathrm{MEM}}$")):
    E0, X, PD = decomp_from_mat(MAT[k], INSTR[k]); case("dilution", lab, E0, X, PD, INSTR[k], "FaBuMe", 1000)
# (2) kernel code, M1 compute
for ver, lab in (("old", "previous kernel"), ("new", "current kernel")):
    M = Mat(os.path.join(D, AB["M1"]), lambda r, v=ver: r["version"] == v and r["regime"] == "cpu")
    ins = {c: kd_instr("M1", ver, "cpu", c) for c in C13}
    E0, X, PD = decomp_from_mat(M, ins); case("kernel code", "M1, " + lab, E0, X, PD, ins, "FaBuMe", 1000)
# (3) dedicated call sites, Machine 2
for topo, lab in (("0", "shared site"), ("1", "one site per layer")):
    M = Mat(os.path.join(D, "M2_results_20261019/M2_B4_energy.csv"), lambda r, t=topo: r["topo"] == t)
    ins = instr_perf(os.path.join(D, "M2_results_20261019/M2_B4_perf.csv"), lambda r, t=topo: r["topo"] == t, 2000, 100,
                     ["base", "Fa", "Bu", "Me", "FaBuMe"])
    E0, X, PD = decomp_from_mat(M, ins); case("call-site topology", "M2, " + lab, E0, X, PD, ins, "FaBuMe", 1000)
# (4) baseline weight w = 8 vs w = 1 (same runs: energy, time and counters)
for w_ in ("1", "8"):
    R = [r for r in csv.DictReader(open(os.path.join(D, "phaseB/B1_perf_weights.csv"))) if r["weight"] == w_]
    K = float(R[0]["K"]); W = float(R[0]["warmup"])
    g = lambda c, col: st.median(float(r[col]) for r in R if r["config"] == c)
    ins = {c: (g(c, "instructions") - S_INSTR) / ((K + W) * NIT) for c in C13}
    E0, t0 = g("base", "energy_J"), g("base", "time_s")
    X = {c: (g(c, "energy_J"), g(c, "time_s"), ins[c]) for c in C13 if c != "base"}
    PD = lmdi(E0, t0, ins["base"], X); PD["_i0"] = ins["base"]
    for c in ("FaBuMe", "StDeAd"):
        case("baseline weight", f"M1, $w = {w_}$, \\texttt{{{c}}}", E0, X, PD, ins, c, K)
# (5) duplicated layers and default JIT
Md = Mat(os.path.join(D, "M1_dispatch_energy_v2.csv"), lambda r: r["dup"] in ("1", "3"),
         key=lambda r: r["config"] if r["dup"] == "1" else r["config"] + "x" + r["dup"])
Rp = list(csv.DictReader(open(os.path.join(D, "M1_dispatch_perf_v2.csv"))))
gi = lambda c, d: (st.median(float(r["instructions"]) for r in Rp if r["config"] == c and r["dup"] == d) - S_INSTR) / (5100 * NIT)
ins = {"base": gi("base", "1"), "Bu": gi("Bu", "1"), "Bux3": gi("Bu", "3"), "BuMe": gi("BuMe", "1"), "Me": gi("Me", "1")}
E0, X, PD = decomp_from_mat(Md, ins)
case("duplicated layers", "M1, \\texttt{Bu}$\\times 3$", E0, X, PD, ins, "Bux3", 1000)
case("duplicated layers", "M1, \\texttt{BuMe}", E0, X, PD, ins, "BuMe", 1000)
for b, lab in (("default", "TC = 0 (measured)"), ("tiered", "default .NET 8 configuration")):
    M = Mat(os.path.join(D, "phaseB/B3_energy.csv"), lambda r, bb=b: r["binary"] == bb and r["dup"] == "1")
    ins = instr_perf(os.path.join(D, "phaseB/B3_perf.csv"), lambda r, bb=b: r["binary"] == bb and r["dup"] == "1", 3000, 400,
                     ["base", "Fa", "Bu", "Me", "FaBuMe"])
    E0, X, PD = decomp_from_mat(M, ins); case("JIT configuration", "M1, " + lab, E0, X, PD, ins, "FaBuMe", 1000)
V["cases"] = CASES

# ------------------------------------------------------------------ M6: signatures, dose-response, allocation
V["sig"] = {k: {p: MAT[k].rho(p) for p in PAT} for k in MAT}
md.append("\n## 6. Signatures, dose-réponse, allocation\n")
md.append("| patron | " + " | ".join(MAT) + " |"); md.append("|---|" + "---|" * len(MAT))
for p in PAT: md.append(f"| {p} | " + " | ".join(f"{V['sig'][k][p]:.3f}" for k in MAT) + " |")
V["dose"] = {}
md.append("\n| cellule | médianes de groupe 0 / 1 / 2 / 3 allouants [IC 95 % passes] | P(super-linéaire) |"); md.append("|---|---|---|")
for k, M in MAT.items():
    groups = {g: [c for c in COMPS if nalloc(c) == g] for g in range(4)}
    reps = sorted(set.intersection(*[set(M.v[x]) for x in M.v]))
    cfgs = list(M.v); A = {x: np.array([M.v[x][r][0] for r in reps]) for x in cfgs}
    Bn = 4000; idx = rng.integers(0, len(reps), (Bn, len(reps)))
    med = {x: np.median(A[x][idx], axis=1) for x in cfgs}
    dl = {c: med[c] - 1 - sum(med[p] - 1 for p in dec(c)) for c in COMPS}
    gm = {g: np.median(np.array([dl[c] for c in groups[g]]), axis=0) for g in range(4)}
    point = {g: 100 * st.median(M.delta(c) for c in groups[g]) for g in range(4)}
    ci = {g: (100 * np.quantile(gm[g], .025), 100 * np.quantile(gm[g], .975)) for g in range(4)}
    psl = float(np.mean((gm[3] - gm[2]) > (gm[2] - gm[1])))
    V["dose"][k] = dict(point=point, ci=ci, psl=psl, n={g: len(groups[g]) for g in range(4)},
                        comps={c: (nalloc(c), 100 * M.delta(c)) for c in COMPS})
    md.append(f"| {k} | " + " / ".join(f"{point[g]:+.1f} [{ci[g][0]:+.1f} ; {ci[g][1]:+.1f}]" for g in range(4)) + f" | {psl:.2f} |")
ALL = {r["config"]: int(r["alloc_per_iter"]) - 40 for r in csv.DictReader(open(os.path.join(D, "M1_alloc_cpu.csv")))}
V["alloc"] = {}
md.append("\n| cellule | r(δ, volume) | r(δ, nb. sources) | 3 comp. à 3 250 088 o | 3 comp. à 39 200 o |"); md.append("|---|---|---|---|---|")
for k, M in MAT.items():
    xs = np.array([ALL[c] for c in COMPS], float); ns = np.array([nalloc(c) for c in COMPS], float)
    ds = np.array([100 * M.delta(c) for c in COMPS])
    big = [c for c in COMPS if ALL[c] == 3250088]; small = [c for c in COMPS if ALL[c] == 39200]
    V["alloc"][k] = dict(r_vol=float(np.corrcoef(xs, ds)[0, 1]), r_src=float(np.corrcoef(ns, ds)[0, 1]),
                         big=(big, min(100 * M.delta(c) for c in big), max(100 * M.delta(c) for c in big)),
                         small=(small, min(100 * M.delta(c) for c in small), max(100 * M.delta(c) for c in small)))
    a = V["alloc"][k]
    md.append(f"| {k} | {a['r_vol']:+.2f} | {a['r_src']:+.2f} | {', '.join(big)} : {a['big'][1]:+.1f} à {a['big'][2]:+.1f} | {', '.join(small)} : {a['small'][1]:+.1f} à {a['small'][2]:+.1f} |")
V["ALLOCVOL"] = ALL

json.dump(V, open(os.path.join(OUT, "values.json"), "w"), indent=1, default=lambda o: o if not isinstance(o, np.generic) else o.item())
json.dump({"SIG": SIG, "SIGOLD": SIGOLD, "COMPS": COMPS}, open(os.path.join(OUT, "sig.json"), "w"), indent=1,
          default=lambda o: o.item() if isinstance(o, np.generic) else o)
open(os.path.join(HERE, "phaseR", "RESULTATS_NOYAU_ACTUEL.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md))
