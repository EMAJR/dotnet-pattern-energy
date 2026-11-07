#!/usr/bin/env python3
# =====================================================================================
# analyse_revision2.py -- offline analyses answering the evaluation report of 19/10.
# No new measurement: every input already exists in data_campaigns/ and phaseA/.
#
#   R1  memory-bound sub-additive interactions on Machine 1 (re-run), listed
#   R2  common-mode baseline bias: does a campaign-level scaling f of all ratios explain the
#       between-campaign shifts?  Prediction: delta' - delta = (f - 1) * (delta - (k - 1))
#   R3  JIT configuration (B3): delta in points of each configuration's own baseline,
#       bootstrap SE, instruction and branch-miss surplus per iteration
#   R4  branch-miss surplus per iteration: topology (B4) and baseline weight (B1)
#   R5  topology (B4): reduction shared -> dedicated with interval, and 90 % upper bounds
#   R6  both significance criteria (z-rule AND Bonferroni-level percentile) for B4 and the
#       dispatch experiment (Tables 6 and 7 of the article)
#   R7  random-effects pooling: DerSimonian-Laird vs REML with Hartung-Knapp interval
#
# Usage: python3 analyse_revision2.py        Output: phaseR/ (CSV + RAPPORT_REVISION_2.md)
# =====================================================================================
import csv, os, math, random, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_campaigns"); PB = os.path.join(DATA, "phaseB")
OUT = os.path.join(HERE, "phaseR"); os.makedirs(OUT, exist_ok=True)
PAT = ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]; ALLOC = {"Fa", "Bu", "Ob", "Me"}
Z = 3.0976; ALPHA = 0.05 / 26; N_IT = 200000
md = []
def P(s=""): md.append(s)
def dec(c): return [c[i:i + 2] for i in range(0, len(c), 2)]
def is_comp(c): return len(dec(c)) >= 2 and all(p in PAT for p in dec(c))
def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def q(v, p):
    v = sorted(v); i = p * (len(v) - 1); lo = int(math.floor(i)); hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)
def wcsv(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows)

def load(path, filt=None, num="e_cfg", den="e_base", key=lambda r: r["config"]):
    R = {}
    for r in csv.DictReader(open(path, newline="")):
        if filt and not filt(r): continue
        a, b = f(r.get(num)), f(r.get(den))
        if a is None or not b: continue
        R.setdefault(key(r), []).append(a / b)
    return R

def parts_of(c):
    """'BuMe' -> ['Bu','Me'];  'Bux3' -> ['Bu','Bu','Bu'] (dup experiment)."""
    if "x" in c: base, d = c.split("x"); return [base] * int(d)
    return dec(c)

def delta(R, c, rng=None):
    pick = (lambda v: st.median(rng.choices(v, k=len(v)))) if rng else st.median
    return pick(R[c]) - (1 + sum(pick(R[p]) - 1 for p in parts_of(c)))

def boot(R, c, B, seed=11):
    rng = random.Random(seed); return [delta(R, c, rng) for _ in range(B)]

def sig(R, c, B=20000):
    d = delta(R, c); bs = boot(R, c, B); se = st.stdev(bs)
    lo, hi = q(bs, ALPHA / 2), q(bs, 1 - ALPHA / 2)
    zr = abs(d) > Z * se; pr = lo > 0 or hi < 0
    return d, se, zr, pr, lo, hi, bs

# =====================================================================================
P("# Analyses de révision 2 (rapport d'évaluation du 19/10)\n")
P("Toutes les entrées existent déjà ; aucune nouvelle mesure. Valeurs en points de l'énergie de baseline.\n")

# ---------------- R1
P("## R1 — Sous-additivités en régime mémoire, Machine 1\n")
A1b = list(csv.DictReader(open(os.path.join(HERE, "phaseA", "A1b_replication_significance.csv"))))
rows = []
for r in A1b:
    if r["campaign"] != "M1-MEM": continue
    for camp, dk, sk in (("record", "delta_record", "robust_sig_record"), ("rerun", "delta_rerun", "robust_sig_rerun")):
        if r[sk] == "1" and f(r[dk]) < 0:
            rows.append([camp, r["composition"], r["n_alloc"], r[dk]])
wcsv("R1_mem_subadditive.csv", ["campaign", "composition", "n_alloc", "delta"], rows)
for camp in ("record", "rerun"):
    L = [x for x in rows if x[0] == camp]
    P(f"- {camp} : {len(L)} sous-additives robustes" + (" — " + ", ".join(f"{x[1]} ({x[3]})" for x in L) if L else ""))
na = [int(x[2]) for x in rows if x[0] == "rerun"]
P(f"- re-exécution : nombre de patrons allouants dans ces compositions = {sorted(na)}\n")

# ---------------- R2
P("## R2 — Biais de mode commun lié à la baseline (prédiction (f−1)(δ−(k−1)))\n")
CPU = [("rec", "M1_cpu.csv", None), ("ET", "M1_cpu_ET.csv", None), ("amp1x", "M1_amp_cpu_1x.csv", None),
       ("sw1", "M1_sweep_cpu.csv", lambda r: r.get("kernel_rep") == "1"),
       ("sw2", "M1_sweep_cpu_v2.csv", lambda r: r.get("kernel_rep") == "1"),
       ("disp1", "M1_dispatch_energy.csv", lambda r: r.get("dup", "1") == "1"),
       ("disp2", "M1_dispatch_energy_v2.csv", lambda r: r.get("dup", "1") == "1")]
RC = {n: load(os.path.join(DATA, fn), flt) for n, fn, flt in CPU}
rho = {n: {c: st.median(v) for c, v in R.items()} for n, R in RC.items()}
D = {n: {c: delta(R, c) for c in R if is_comp(c) and all(p in R for p in dec(c))} for n, R in RC.items()}
ref_rho = {p: st.median([rho[n][p] for n in rho if p in rho[n]]) for p in PAT}
ref_d = {c: st.median([D[n][c] for n in D if c in D[n]]) for c in set().union(*D.values())}
rows = []
P("| campagne | f (signatures isolées / médiane) | δ FaBuMe observé − réf. | prédit par f | corr. obs/prédit (toutes compositions communes) |")
P("|---|---|---|---|---|")
for n in rho:
    fs = st.median([rho[n][p] / ref_rho[p] for p in PAT if p in rho[n]])
    comps = [c for c in D[n] if c in ref_d]
    obs = [D[n][c] - ref_d[c] for c in comps]
    pred = [(fs - 1) * (ref_d[c] - (len(dec(c)) - 1)) for c in comps]
    r = (st.correlation(obs, pred) if len(comps) > 2 and st.pstdev(pred) > 0 else float("nan"))
    fo = D[n].get("FaBuMe", float("nan")) - ref_d.get("FaBuMe", float("nan"))
    fp = (fs - 1) * (ref_d["FaBuMe"] - 2) if "FaBuMe" in ref_d else float("nan")
    rows.append([n, round(fs, 4), round(100 * fo, 1), round(100 * fp, 1), round(r, 2), len(comps)])
    P(f"| {n} | {fs:.3f} | {100*fo:+.1f} | {100*fp:+.1f} | {r:+.2f} (n={len(comps)}) |")
wcsv("R2_common_mode.csv", ["campaign", "f", "obs_FaBuMe_shift", "pred_FaBuMe_shift", "corr_obs_pred", "n_comp"], rows)
# memory record vs re-run
RM = {"rec": load(os.path.join(DATA, "M1_mem.csv")), "ET": load(os.path.join(DATA, "M1_mem_ET.csv"))}
rm = {n: {c: st.median(v) for c, v in R.items()} for n, R in RM.items()}
fm = st.median([rm["ET"][p] / rm["rec"][p] for p in PAT])
cm = [c for c in RM["rec"] if is_comp(c) and c in RM["ET"]]
obs = [delta(RM["ET"], c) - delta(RM["rec"], c) for c in cm]
pred = [(fm - 1) * (delta(RM["rec"], c) - (len(dec(c)) - 1)) for c in cm]
sl = sum(o * p for o, p in zip(obs, pred)) / sum(p * p for p in pred)
P(f"\nRégime mémoire M1, re-exécution vs référence : f = {fm:.3f} ; corrélation observé/prédit = "
  f"{st.correlation(obs, pred):+.2f} ; pente = {sl:.2f} (1 = biais de mode commun pur) ; "
  f"décalage moyen observé {100*st.mean(obs):+.1f} pts, prédit {100*st.mean(pred):+.1f} pts.\n")
wcsv("R2_mem_rec_vs_rerun.csv", ["composition", "k", "obs_shift", "pred_shift"],
     [[c, len(dec(c)), round(100 * o, 2), round(100 * p, 2)] for c, o, p in zip(cm, obs, pred)])

# ---------------- R3
P("## R3 — Configuration JIT (B3) : δ relatifs, inférence, compteurs\n")
B3E = list(csv.DictReader(open(os.path.join(PB, "B3_energy.csv"))))
B3P = list(csv.DictReader(open(os.path.join(PB, "B3_perf.csv"))))
key = lambda r: r["config"] + ("x" + r["dup"] if r["dup"] != "1" else "")
rows = []
P("| config | binaire | δ (pts) | 2·SE | z-rule | percentile | excès (J/1000 t.) | surplus instr./itér. | surplus br-miss/itér. |")
P("|---|---|---|---|---|---|---|---|---|")
for b in ("default", "tiered"):
    R = load(os.path.join(PB, "B3_energy.csv"), lambda r, b=b: r["binary"] == b, key=key)
    base_e = st.median([f(r["e_base"]) for r in B3E if r["binary"] == b])
    M = {}
    for r in B3P:
        if r["binary"] != b: continue
        M.setdefault(key(r), {"ins": [], "bm": [], "K": int(r["K"]) + int(r["warmup"])})
        M[key(r)]["ins"].append(f(r["instructions"])); M[key(r)]["bm"].append(f(r["branch_misses"]))
    def surplus(c, col):
        if "base" not in M or c not in M: return float("nan")
        b0 = st.median(M["base"][col]); x = st.median(M[c][col])
        return ((x - b0) - sum(st.median(M[p][col]) - b0 for p in parts_of(c))) / (M[c]["K"] * N_IT)
    for c in ["FaBuMe", "BuMe", "ObMe", "Bux2", "Bux3", "StDeAd"]:
        if c not in R or not all(p in R for p in parts_of(c)): continue
        d, se, zr, pr, lo, hi, _ = sig(R, c, 8000)
        rows.append([c, b, round(100 * d, 1), round(200 * se, 1), int(zr), int(pr), round(d * base_e, 2),
                     round(surplus(c, "ins"), 2), round(surplus(c, "bm"), 4)])
        P(f"| {c} | {b} | {100*d:+.1f} | {200*se:.1f} | {'oui' if zr else 'non'} | {'oui' if pr else 'non'} | "
          f"{d*base_e:+.2f} | {surplus(c,'ins'):.2f} | {surplus(c,'bm'):.4f} |")
    P(f"| (baseline {b} : {base_e:.2f} J/1000 tâches) |||||||||")
wcsv("R3_jit.csv", ["config", "binary", "delta_pts", "2SE", "z_rule", "percentile", "excess_J", "instr_surplus_iter", "brmiss_surplus_iter"], rows)

# ---------------- R4 + R5 + R6 (B4)
P("\n## R4/R5/R6 — Topologie (B4) : double critère, réduction, bornes, branch-misses\n")
B4P = list(csv.DictReader(open(os.path.join(PB, "B4_perf.csv"))))
rows = []; boots = {}
P("| comp. | topo | δ | 2·SE | z | perc. | borne sup. 90 % | br-miss/itér. |")
P("|---|---|---|---|---|---|---|---|")
for t in ("0", "1", "2"):
    R = load(os.path.join(PB, "B4_energy.csv"), lambda r, t=t: r["topo"] == t)
    M = {}
    for r in B4P:
        if r["topo"] != t: continue
        M.setdefault(r["config"], {"bm": [], "K": int(r["K"]) + int(r["warmup"])})["bm"].append(f(r["branch_misses"]))
    for c in ["FaBu", "BuMe", "BuOb", "ObMe", "FaBuMe", "BuObMe", "StDeAd"]:
        d, se, zr, pr, lo, hi, bs = sig(R, c)
        boots[(c, t)] = (d, bs)
        b0 = st.median(M["base"]["bm"])
        bm = ((st.median(M[c]["bm"]) - b0) - sum(st.median(M[p]["bm"]) - b0 for p in dec(c))) / (M[c]["K"] * N_IT)
        rows.append([c, t, round(100 * d, 1), round(200 * se, 1), int(zr), int(pr), round(100 * q(bs, 0.95), 1), round(bm, 4)])
        P(f"| {c} | {t} | {100*d:+.1f} | {200*se:.1f} | {'oui' if zr else 'non'} | {'oui' if pr else 'non'} | {100*q(bs,0.95):+.1f} | {bm:.4f} |")
wcsv("R6_topology_both_criteria.csv", ["comp", "topo", "delta", "2SE", "z_rule", "percentile", "upper90", "brmiss_surplus_iter"], rows)
P("\nRéduction partagé → un site par couche (différence de deux bootstraps indépendants) :\n")
rows = []
for c in ["FaBu", "BuMe", "BuOb", "ObMe", "FaBuMe", "BuObMe"]:
    d0, b0 = boots[(c, "0")]; d1, b1 = boots[(c, "1")]
    diff = [x - y for x, y in zip(b0, b1)]; se = st.stdev(diff)
    rows.append([c, round(100 * (d0 - d1), 1), round(200 * se, 1), round(100 * q(diff, 0.025), 1), round((d0 - d1) / se, 1)])
    P(f"- {c} : réduction {100*(d0-d1):+.1f} pts (IC 95 % bas {100*q(diff,0.025):+.1f} ; z = {(d0-d1)/se:.1f})")
wcsv("R5_topology_reduction.csv", ["comp", "reduction_pts", "2SE", "ci95_low", "z"], rows)

# R6 dispatch experiment (Table 6)
P("\n## R6 — Expérience dispatch (Tableau 6), double critère\n")
R = load(os.path.join(DATA, "M1_dispatch_energy_v2.csv"), key=key)
rows = []
for c in ["Bux2", "Mex2", "Obx2", "Bux3", "Mex3", "BuMe", "ObMe", "FaBuMe", "StDeAd"]:
    if c not in R: continue
    d, se, zr, pr, lo, hi, _ = sig(R, c)
    rows.append([c, round(100 * d, 1), round(200 * se, 1), int(zr), int(pr)])
    P(f"- {c} : δ {100*d:+.1f} (2·SE {200*se:.1f}) — z-rule {'oui' if zr else 'non'}, percentile {'oui' if pr else 'non'}")
wcsv("R6_dispatch_both_criteria.csv", ["config", "delta", "2SE", "z_rule", "percentile"], rows)

# R4 branch misses vs weight (B1)
P("\n## R4 — Branch-misses selon le poids (B1)\n")
B1 = list(csv.DictReader(open(os.path.join(PB, "B1_perf_weights.csv"))))
rows = []
for w in sorted({int(r["weight"]) for r in B1}):
    M = {}
    for r in B1:
        if int(r["weight"]) != w: continue
        M.setdefault(r["config"], {"bm": [], "cy": [], "K": int(r["K"]) + int(r["warmup"])})
        M[r["config"]]["bm"].append(f(r["branch_misses"])); M[r["config"]]["cy"].append(f(r["cycles"]))
    for c in ["FaBuMe", "BuMe", "StDeAd"]:
        def s(col):
            b0 = st.median(M["base"][col])
            return ((st.median(M[c][col]) - b0) - sum(st.median(M[p][col]) - b0 for p in dec(c))) / (M[c]["K"] * N_IT)
        rows.append([w, c, round(s("bm"), 4), round(s("cy"), 1)])
    P(f"- w = {w} : surplus br-miss/itér. FaBuMe {rows[-3][2]:.4f}, BuMe {rows[-2][2]:.4f}, StDeAd {rows[-1][2]:.4f} ; "
      f"surplus cycles FaBuMe {rows[-3][3]:+.1f}")
wcsv("R4_brmiss_weights.csv", ["w", "comp", "brmiss_surplus_iter", "cycles_surplus_iter"], rows)

# ---------------- R7
P("\n## R7 — Pooling : DerSimonian–Laird vs REML + Hartung–Knapp\n")
def dl(v):
    k = len(v); w = [1 / s ** 2 for _, s in v]; fe = sum(a * d for a, (d, _) in zip(w, v)) / sum(w)
    Qs = sum(a * (d - fe) ** 2 for a, (d, _) in zip(w, v)); C = sum(w) - sum(a * a for a in w) / sum(w)
    return max(0.0, (Qs - (k - 1)) / C)
def reml(v):
    t2 = dl(v)
    for _ in range(500):
        w = [1 / (s ** 2 + t2) for _, s in v]; mu = sum(a * d for a, (d, _) in zip(w, v)) / sum(w)
        new = max(0.0, sum(a * a * ((d - mu) ** 2 - s ** 2) for a, (d, s) in zip(w, v)) / sum(a * a for a in w) + 1 / sum(w))
        if abs(new - t2) < 1e-12: break
        t2 = new
    return t2
TQ = {4: 2.776, 5: 2.571, 6: 2.447}   # t(0.975, k-1)
rows = []
P("| composition | k | DL : pooled ± 2SE | REML + HK : pooled [IC 95 %] | τ REML |")
P("|---|---|---|---|---|")
for c in ["FaBuMe", "BuObMe", "BuMe", "ObMe", "StDeAd"]:
    v = []
    for n, R in RC.items():
        if c in R and all(p in R for p in dec(c)):
            v.append((delta(R, c), st.stdev(boot(R, c, 1500, 3))))
    k = len(v)
    t2 = dl(v); w = [1 / (s ** 2 + t2) for _, s in v]; mu = sum(a * d for a, (d, _) in zip(w, v)) / sum(w); se = math.sqrt(1 / sum(w))
    t2r = reml(v); wr = [1 / (s ** 2 + t2r) for _, s in v]; mur = sum(a * d for a, (d, _) in zip(wr, v)) / sum(wr)
    hk = math.sqrt(sum(a * (d - mur) ** 2 for a, (d, _) in zip(wr, v)) / ((k - 1) * sum(wr)))
    tq = TQ.get(k - 1 + 1, 2.0) if False else {3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365}[k - 1 + 0] if k - 1 in (3, 4, 5, 6, 7) else 2.0
    lo, hi = mur - tq * hk, mur + tq * hk
    rows.append([c, k, round(100 * mu, 1), round(200 * se, 1), round(100 * mur, 1), round(100 * lo, 1), round(100 * hi, 1), round(100 * math.sqrt(t2r), 1)])
    P(f"| {c} | {k} | {100*mu:+.1f} ± {200*se:.1f} | {100*mur:+.1f} [{100*lo:+.1f} ; {100*hi:+.1f}] | {100*math.sqrt(t2r):.1f} |")
wcsv("R7_pooling.csv", ["comp", "k", "DL", "DL_2SE", "REML", "HK_lo95", "HK_hi95", "tau_REML"], rows)

open(os.path.join(OUT, "RAPPORT_REVISION_2.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md))
