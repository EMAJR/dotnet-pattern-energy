# =====================================================================================
# Checks requested by the review of PLAN_REVISION_5 (no new measurement).
#   V1  current-kernel matrices (M1 ET, M2 19/10): significance, sub-additivity, ordering,
#       dose-response by number of allocating patterns
#   V2  pooling of FaBuMe (M1 CPU) over every current-kernel campaign: Q, DL, REML + HK
#   V3  the two dispatch campaigns (both current kernel): energy shifts
#   V4  topology: shared - dedicated contrast and double difference with the control
#   V5  kernel diagnosis: startup-free factor (internal timer) and K/protocol dependence (M2 MEM)
#   V6  compute -> memory contraction in points, in joules and in cycles
# Usage: python3 analyse_revision5.py        Output: phaseR/RAPPORT_REVISION_5_VERIF.md
# =====================================================================================
import csv, os, math, random, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data_campaigns"); OUT = os.path.join(HERE, "phaseR")
PAT = ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]; ALLOC = {"Fa", "Bu", "Ob", "Me"}
Z = 3.0976; ALPHA = 0.05 / 26
md = []
def P(s=""): md.append(s); print(s)
def dec(c): return [c[i:i + 2] for i in range(0, len(c), 2)]
def q(v, p):
    v = sorted(v); i = p * (len(v) - 1); lo = int(i); hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)
def load(path, filt=lambda r: True, num="e_cfg", den="e_base"):
    R = {}; EB = []
    for r in csv.DictReader(open(path)):
        if not filt(r): continue
        R.setdefault(r["config"], []).append(float(r[num]) / float(r[den])); EB.append(float(r[den]))
    return R, st.median(EB)
def delta(R, c, rng=None):
    pick = (lambda v: st.median(rng.choices(v, k=len(v)))) if rng else st.median
    return pick(R[c]) - (1 + sum(pick(R[p]) - 1 for p in dec(c)))
def sig(R, c, B):
    d = delta(R, c); rng = random.Random(11); bs = [delta(R, c, rng) for _ in range(B)]
    se = st.stdev(bs); lo, hi = q(bs, ALPHA / 2), q(bs, 1 - ALPHA / 2)
    return d, se, abs(d) > Z * se, (lo > 0 or hi < 0)

CAMP = {"M1-CPU": "M1_cpu_ET.csv", "M1-MEM": "M1_mem_ET.csv",
        "M2-CPU": "M2_results_20261019/M2_repl_cpu_time.csv", "M2-MEM": "M2_results_20261019/M2_repl_mem_time.csv"}
P("# Vérifications demandées par la relecture du plan de révision 5\n")
P("## V1 — Matrices du noyau actuel (M1 ET, M2 19/10), B = 20 000\n")
P("| cellule | * super | * sub | † super | † sub | sous-additives (*) | StFa | FaBuMe | BuMe | médiane δ par nb. de patrons allouants (1 / 2 / 3) |")
P("|---|---|---|---|---|---|---|---|---|---|")
MAT = {}
for lab, fn in CAMP.items():
    R, eb = load(os.path.join(D, fn)); MAT[lab] = (R, eb)
    comps = [c for c in R if len(c) > 2]
    res = {c: sig(R, c, 20000) for c in comps}
    star = {c for c, v in res.items() if v[2] and v[3]}; dag = {c for c, v in res.items() if v[2] and not v[3]}
    sup = lambda S: sum(1 for c in S if res[c][0] > 0); sub = lambda S: sum(1 for c in S if res[c][0] < 0)
    subl = ", ".join(f"{c} {100*res[c][0]:+.1f}" for c in sorted(star, key=lambda c: res[c][0]) if res[c][0] < 0)
    g = {}
    for c in comps: g.setdefault(sum(p in ALLOC for p in dec(c)), []).append(100 * res[c][0])
    gm = " / ".join(f"{st.median(g[k]):+.1f}" for k in (1, 2, 3) if k in g)
    P(f"| {lab} | {sup(star)} | {sub(star)} | {sup(dag)} | {sub(dag)} | {subl or '—'} | {100*res['StFa'][0]:+.1f}{'*' if 'StFa' in star else ('†' if 'StFa' in dag else '')} | {100*res['FaBuMe'][0]:+.1f} | {100*res['BuMe'][0]:+.1f} | {gm} |")
    with open(os.path.join(OUT, f"R5_matrix_{lab}.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["comp", "delta_pct", "se_pct", "zrule", "pctrule"])
        for c in sorted(comps): w.writerow([c, round(100 * res[c][0], 2), round(100 * res[c][1], 2), res[c][2], res[c][3]])

# ---------------- V2
P("\n## V2 — Pooling FaBuMe, M1 calcul, toutes les campagnes du noyau actuel\n")
def boot_se(R, c, B=3000):
    rng = random.Random(3); return st.stdev([delta(R, c, rng) for _ in range(B)])
src = [("matrice ET (26 comp., 15 rép.)", os.path.join(D, "M1_cpu_ET.csv"), lambda r: True),
       ("A/B, version actuelle (10 rép.)", os.path.join(D, "M1_code_ab_20261020.csv"), lambda r: r["version"] == "new" and r["regime"] == "cpu"),
       ("dispatch v2, dup = 1 (8 rép.)", os.path.join(D, "M1_dispatch_energy_v2.csv"), lambda r: r["dup"] == "1"),
       ("topologie 1, site partagé (B4)", os.path.join(D, "phaseB/B4_energy.csv"), lambda r: r["topo"] == "0"),
       ("topologie 2, site partagé (B4 bis)", os.path.join(D, "phaseB/B4_energy_rep2.csv"), lambda r: r["topo"] == "0"),
       ("balayage v1, w = 1", os.path.join(D, "M1_sweep_cpu.csv"), lambda r: r["kernel_rep"] == "1"),
       ("balayage v2, w = 1", os.path.join(D, "M1_sweep_cpu_v2.csv"), lambda r: r["kernel_rep"] == "1"),
       ("amplification 1× (8 rép.)", os.path.join(D, "M1_amp_cpu_1x.csv"), lambda r: True)]
v = []
P("| campagne | n | FaBuMe | 2·SE |"); P("|---|---|---|---|")
for lab, fn, flt in src:
    if not os.path.exists(fn): P(f"| {lab} | absent | | |"); continue
    try:
        R, _ = load(fn, flt)
        if not all(k in R for k in ["FaBuMe", "Fa", "Bu", "Me"]): P(f"| {lab} | FaBuMe absent | | |"); continue
        d, s = delta(R, "FaBuMe"), boot_se(R, "FaBuMe"); v.append((lab, d, s))
        P(f"| {lab} | {len(R['FaBuMe'])} | {100*d:+.1f} | {200*s:.1f} |")
    except KeyError as e: P(f"| {lab} | colonne {e} absente | | |")
def pool(vv):
    k = len(vv); w = [1 / s ** 2 for _, _, s in vv]; fe = sum(a * d for a, (_, d, _) in zip(w, vv)) / sum(w)
    Qs = sum(a * (d - fe) ** 2 for a, (_, d, _) in zip(w, vv)); C = sum(w) - sum(a * a for a in w) / sum(w)
    t2 = max(0.0, (Qs - (k - 1)) / C); wd = [1 / (s ** 2 + t2) for _, _, s in vv]
    mu = sum(a * d for a, (_, d, _) in zip(wd, vv)) / sum(wd); se = math.sqrt(1 / sum(wd))
    t2r = t2
    for _ in range(500):
        wr = [1 / (s ** 2 + t2r) for _, _, s in vv]; m = sum(a * d for a, (_, d, _) in zip(wr, vv)) / sum(wr)
        new = max(0.0, sum(a * a * ((d - m) ** 2 - s ** 2) for a, (_, d, s) in zip(wr, vv)) / sum(a * a for a in wr) + 1 / sum(wr))
        if abs(new - t2r) < 1e-12: break
        t2r = new
    wr = [1 / (s ** 2 + t2r) for _, _, s in vv]; mur = sum(a * d for a, (_, d, _) in zip(wr, vv)) / sum(wr)
    hk = math.sqrt(sum(a * (d - mur) ** 2 for a, (_, d, _) in zip(wr, vv)) / ((k - 1) * sum(wr)))
    tq = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306}[k - 1]
    I2 = max(0.0, (Qs - (k - 1)) / Qs) if Qs > 0 else 0.0
    return k, Qs, mu, se, math.sqrt(t2), mur, mur - tq * hk, mur + tq * hk, math.sqrt(t2r), I2
for lab, sel in [("toutes", v), ("sans A/B", [x for x in v if not x[0].startswith("A/B")])]:
    k, Qs, mu, se, t, mur, lo, hi, tr, I2 = pool(sel)
    P(f"\n- **{lab}** (k = {k}) : Q = {Qs:.1f} (ddl {k-1}), I² = {100*I2:.0f} % ; DL {100*mu:+.1f} ± {200*se:.1f}, τ_DL = {100*t:.1f} ; "
      f"REML + HK {100*mur:+.1f} [{100*lo:+.1f} ; {100*hi:+.1f}], τ_REML = {100*tr:.1f}")

# ---------------- V3
P("\n## V3 — Les deux campagnes de dispatch (noyau actuel toutes deux)\n")
R1, _ = load(os.path.join(D, "M1_dispatch_energy.csv"), lambda r: r["dup"] == "1")
R2, _ = load(os.path.join(D, "M1_dispatch_energy_v2.csv"), lambda r: r["dup"] == "1")
for c in ["BuMe", "ObMe", "StDeAd"]:
    if c in R1 and c in R2 and all(p in R1 and p in R2 for p in dec(c)):
        P(f"- {c} : v1 {100*delta(R1,c):+.1f}, v2 {100*delta(R2,c):+.1f} (écart {100*(delta(R2,c)-delta(R1,c)):+.1f})")

# ---------------- V4
P("\n## V4 — Topologie : contraste partagé − dédié et double différence avec le témoin\n")
P("| campagne | comp. | δ partagé | δ dédié | partagé − dédié | double différence (− témoin) | Δ instr. partagé / dédié |")
P("|---|---|---|---|---|---|---|")
def perf_surplus(fn, topo, c):
    if not os.path.exists(fn): return None
    M = {}
    for r in csv.DictReader(open(fn)):
        if r["topo"] == topo: M.setdefault(r["config"], []).append(r)
    if "base" not in M or c not in M: return None
    m = lambda x: st.median(float(r["instructions"]) for r in M[x])
    K = float(M["base"][0]["K"]) + float(M["base"][0].get("warmup", 100)); b = m("base")
    return ((m(c) - b) - sum(m(p) - b for p in dec(c))) / (K * 200000)
for lab, fe, fp in [("M1 B4", "phaseB/B4_energy.csv", "phaseB/B4_perf.csv"), ("M1 B4 bis", "phaseB/B4_energy_rep2.csv", "phaseB/B4_perf_rep2.csv"),
                    ("M2 19/10", "M2_results_20261019/M2_B4_energy.csv", "M2_results_20261019/M2_B4_perf.csv"),
                    ("M2 20/10", "M2b_results_20261020/M2b_B4_energy.csv", "M2b_results_20261020/M2b_B4_perf.csv")]:
    fe = os.path.join(D, fe); fp = os.path.join(D, fp)
    if not os.path.exists(fe): continue
    T = {t: load(fe, lambda r, t=t: r["topo"] == t)[0] for t in "01"}
    ctl = delta(T["0"], "StDeAd") - delta(T["1"], "StDeAd")
    for c in ["FaBuMe", "BuObMe", "BuMe", "FaBu", "ObMe", "StDeAd"]:
        s0, s1 = delta(T["0"], c), delta(T["1"], c)
        i0, i1 = perf_surplus(fp, "0", c), perf_surplus(fp, "1", c)
        ins = f"{i0:.1f} / {i1:.1f}" if i0 is not None and i1 is not None else "—"
        P(f"| {lab} | {c} | {100*s0:+.1f} | {100*s1:+.1f} | {100*(s0-s1):+.1f} | {100*(s0-s1-ctl):+.1f} | {ins} |")

# ---------------- V5
P("\n## V5 — Diagnostic : facteur sans démarrage (chronomètre interne) et dépendance au protocole (M2 mémoire)\n")
for host in ["kdiag_machine1", "kdiag_machine2"]:
    R = list(csv.DictReader(open(os.path.join(D, "kdiag_20261020", host, "kdiag_perf.csv"))))
    med = lambda v, reg, c, col: st.median(float(r[col]) for r in R if r["version"] == v and r["regime"] == reg and r["config"] == c)
    for reg in ("cpu", "mem"):
        to, tn = med("old", reg, "base", "time_s"), med("new", reg, "base", "time_s")
        P(f"- {host[6:]} {reg} : temps interne de la baseline ancien {to:.2f} s / actuel {tn:.2f} s → facteur {to/tn:.2f}")
P("\nδ en temps, même binaire, deux protocoles (diagnostic K = 500 sous perf / A/B K = 1000) :")
for host, ab in [("kdiag_machine1", "M1_code_ab_20261020.csv"), ("kdiag_machine2", "M2b_results_20261020/M2b_code_ab.csv")]:
    R = list(csv.DictReader(open(os.path.join(D, "kdiag_20261020", host, "kdiag_perf.csv"))))
    A = list(csv.DictReader(open(os.path.join(D, ab))))
    for reg in ("cpu", "mem"):
        for ver in ("old", "new"):
            med = lambda c: st.median(float(r["time_s"]) for r in R if r["version"] == ver and r["regime"] == reg and r["config"] == c)
            b = med("base"); dk = ((med("FaBuMe") - b) - sum(med(p) - b for p in dec("FaBuMe"))) / b
            RA = {}
            for r in A:
                if r["version"] == ver and r["regime"] == reg: RA.setdefault(r["config"], []).append(float(r["t_cfg"]) / float(r["t_base"]))
            da = delta(RA, "FaBuMe")
            P(f"- {host[6:16]} {reg} {ver} : FaBuMe diagnostic {100*dk:+.1f} / A/B {100*da:+.1f} (rapport {dk/da:.2f})")

# ---------------- V6
P("\n## V6 — Contraction calcul → mémoire : points, joules (pour 1000 tâches), cycles\n")
P("| machine | comp. | δ calcul / mémoire (points) | excès calcul / mémoire (J) | excès en cycles/itér. calcul / mémoire (diagnostic, noyau actuel) |")
P("|---|---|---|---|---|")
for m, host in [("M1", "kdiag_machine1"), ("M2", "kdiag_machine2")]:
    R = list(csv.DictReader(open(os.path.join(D, "kdiag_20261020", host, "kdiag_perf.csv"))))
    def cyc(reg, c):
        med = lambda x: st.median(float(r["cycles"]) for r in R if r["version"] == "new" and r["regime"] == reg and r["config"] == x)
        b = med("base"); return ((med(c) - b) - sum(med(p) - b for p in dec(c))) / (600 * 200000)
    (Rc, ebc), (Rm, ebm) = MAT[m + "-CPU"], MAT[m + "-MEM"]
    for c in ["FaBuMe", "BuObMe", "BuMe", "ObMe"]:
        dc, dm = delta(Rc, c), delta(Rm, c)
        P(f"| {m} | {c} | {100*dc:+.1f} / {100*dm:+.1f} | {dc*ebc:.2f} / {dm*ebm:.2f} | {cyc('cpu', c):+.1f} / {cyc('mem', c):+.1f} |")
    P(f"| {m} | baseline | | {ebc:.2f} / {ebm:.2f} J | |")

open(os.path.join(OUT, "RAPPORT_REVISION_5_VERIF.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
