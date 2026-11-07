#!/usr/bin/env python3
# =====================================================================================
# analyse_phaseA.py -- phase A of the revision plan: offline re-analysis of the EXISTING
# campaigns, no new measurement. Every number of the review response comes from here.
#
#   A1  inter-campaign table for the 26 compositions + random-effects pooling (DerSimonian-
#       Laird): pooled delta, between-campaign SD tau, heterogeneity I^2
#   A2  pass-blocked bootstrap (composition and constituents resampled on the SAME passes)
#       vs the independent bootstrap used in the paper
#   A3  delta in both normalisations: points of baseline (paper) and % of additive prediction
#   A4  audit of the dagger rule: z-rule vs Bonferroni-level percentile interval
#   A5  dose-response medians with bootstrap intervals and group sizes
#   A6  campaign inventory (provenance table)
#   A7  energy vs time interaction per campaign (r, slope, ratio range)
#   A8  per-iteration instruction counts with the correct divisor K + 100 warm-up tasks
#
# Reuses analyse_bootstrap.py (the paper's single source of truth) for the record campaigns,
# so the published values are reproduced exactly before anything new is computed.
#
# Usage:  python3 analyse_phaseA.py        Output: phaseA/  (CSV + RAPPORT_PHASE_A.md + .tex)
# =====================================================================================
import csv, os, math, random, statistics as st, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_campaigns")
OUT = os.path.join(HERE, "phaseA")
os.makedirs(OUT, exist_ok=True)

spec = importlib.util.spec_from_file_location("ab", os.path.join(HERE, "analyse_bootstrap.py"))
ab = importlib.util.module_from_spec(spec); spec.loader.exec_module(ab)
PATTERNS, ALLOC, Z, ALPHA = ab.PATTERNS, ab.ALLOCATING, ab.Z_BONFERRONI, ab.ALPHA
N_ITER = 200000

def dec(s): return [s[i:i + 2] for i in range(0, len(s), 2)]
def is_comp(c): p = dec(c); return len(p) >= 2 and all(x in PATTERNS for x in p)
def n_alloc(c): return sum(1 for p in dec(c) if p in ALLOC)
def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None

# ------------------------------------------------------------------ campaign registry
def f_w(w): return lambda r: r.get("kernel_rep") == str(w)
def f_dup1(r): return r.get("dup", "1") == "1"
CAMPAIGNS = [
  # id, machine, regime, file, row filter, status, K, measured, note
  ("M1-CPU-rec",    "M1", "CPU", "M1_cpu.csv",             None,     "record",    1000, "2026-09-05", "Table 2; .NET 8.0.130, kernel 6.8.0-136"),
  ("M1-CPU-ET",     "M1", "CPU", "M1_cpu_ET.csv",          None,     "replicate", 1000, "oct. (à confirmer)", "re-run with time capture"),
  ("M1-CPU-amp1x",  "M1", "CPU", "M1_amp_cpu_1x.csv",      None,     "replicate", 1000, "oct. (à confirmer)", "amplification, nominal load, reduced set"),
  ("M1-CPU-amp5x",  "M1", "CPU", "M1_amp_cpu_5x.csv",      None,     "other-load",1000, "oct. (à confirmer)", "amplification, n = 10^6 (not pooled)"),
  ("M1-CPU-sw1w1",  "M1", "CPU", "M1_sweep_cpu.csv",       f_w(1),   "replicate", 1000, "oct. (à confirmer)", "weight sweep v1, w = 1"),
  ("M1-CPU-sw2w1",  "M1", "CPU", "M1_sweep_cpu_v2.csv",    f_w(1),   "replicate", 1000, "oct. (à confirmer)", "weight sweep v2, w = 1"),
  ("M1-CPU-disp1",  "M1", "CPU", "M1_dispatch_energy.csv", f_dup1,   "replicate", 1000, "oct. (à confirmer)", "dispatch v1, dup = 1 only"),
  ("M1-CPU-disp2",  "M1", "CPU", "M1_dispatch_energy_v2.csv", f_dup1,"replicate", 1000, "oct. (à confirmer)", "dispatch v2, dup = 1 only"),
  ("M1-MEM-rec",    "M1", "MEM", "M1_mem.csv",             None,     "record",    1000, "2026-09-05", "Table 2"),
  ("M1-MEM-ET",     "M1", "MEM", "M1_mem_ET.csv",          None,     "replicate", 1000, "oct. (à confirmer)", "re-run with time capture"),
  ("M2-CPU-rec",    "M2", "CPU", "M2_cpu.csv",             None,     "record",    1000, "2026-09-24", "Table 2; .NET 8.0.131, kernel 6.8.0-139"),
  ("M2-MEM-rec",    "M2", "MEM", "M2_mem.csv",             None,     "record",    1000, "2026-09-24", "Table 2"),
  ("M2-CPU-SEP06",  "M2", "CPU", "M2_cpu_SEP06_unlocked.csv", None,  "excluded",  1000, "2026-09-06", "governor NOT locked (scaling 30 %)"),
  ("M2-MEM-SEP06",  "M2", "MEM", "M2_mem_SEP06_unlocked.csv", None,  "excluded",  1000, "2026-09-06", "governor NOT locked"),
]
POOLABLE = {"record", "replicate"}

def load(fname, filt=None, num="e_cfg", den="e_base"):
    """{config: {rep: ratio}}"""
    R = {}
    with open(os.path.join(DATA, fname), newline="") as f:
        for row in csv.DictReader(f):
            if filt and not filt(row): continue
            if num not in row or den not in row: return None
            a, b = fnum(row[num]), fnum(row[den])
            if a is None or not b: continue
            R.setdefault(row["config"], {})[row["rep"]] = a / b
    return R

def deltas_point(R):
    rho = {c: st.median(v.values()) for c, v in R.items()}
    out = {}
    for c in rho:
        if is_comp(c) and all(p in rho for p in dec(c)):
            add = 1 + sum(rho[p] - 1 for p in dec(c))
            out[c] = (rho[c] - add, add, rho[c])
    return out, rho

def boot_indep(R, comps, B, seed):
    rng = random.Random(seed); res = {c: [] for c in comps}
    lists = {c: list(v.values()) for c, v in R.items()}
    for c in comps:
        parts = dec(c)
        for _ in range(B):
            rc = st.median(rng.choices(lists[c], k=len(lists[c])))
            add = 1 + sum(st.median(rng.choices(lists[p], k=len(lists[p]))) - 1 for p in parts)
            res[c].append(rc - add)
    return res

def boot_blocked(R, comps, B, seed):
    """Resample PASSES: composition and constituents keep the pass they were measured in."""
    rng = random.Random(seed); res = {c: [] for c in comps}
    needed = set(comps) | {p for c in comps for p in dec(c)}
    reps = sorted(set.intersection(*[set(R[c].keys()) for c in needed]))
    for _ in range(B):
        draw = rng.choices(reps, k=len(reps))
        rho = {c: st.median([R[c][r] for r in draw]) for c in needed}
        for c in comps:
            res[c].append(rho[c] - (1 + sum(rho[p] - 1 for p in dec(c))))
    return res, len(reps)

def pct(sorted_vals, q): return ab.percentile(sorted_vals, q)

def write_csv(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

md = []   # markdown report lines
def H(s): md.append("\n" + s + "\n")
def P(s=""): md.append(s)

# =====================================================================================
# load everything once
# =====================================================================================
camp = {}
for cid, mach, reg, fn, filt, status, K, date, note in CAMPAIGNS:
    if not os.path.exists(os.path.join(DATA, fn)): continue
    R = load(fn, filt)
    if not R: continue
    d, rho = deltas_point(R)
    camp[cid] = dict(machine=mach, regime=reg, file=fn, status=status, K=K, date=date, note=note,
                     R=R, deltas=d, rho=rho,
                     n_reps=st.median([len(v) for v in R.values()]),
                     n_cfg=len(R), has_time=load(fn, filt, "t_cfg", "t_base") is not None)

# =====================================================================================
# A0 -- reproduce the published values first (guard against silent drift)
# =====================================================================================
published = {}
for label, fn in ab.CAMPAIGNS:
    rho, res = ab.analyse(label, os.path.join(DATA, fn))
    published[label] = {r["config"]: r for r in res}
chk = published["M1-CPU"]["FaBuMe"]
assert abs(chk["delta"] * 100 - 93.0) < 0.05, "published M1-CPU FaBuMe not reproduced"

# =====================================================================================
# A1 -- inter-campaign table + random-effects pooling
# =====================================================================================
B_REP = 2000
se_cache = {}
for cid, c in camp.items():
    comps = sorted(c["deltas"])
    bs = boot_indep(c["R"], comps, B_REP, 7)
    se_cache[cid] = {k: st.stdev(v) for k, v in bs.items()}

def dl_pool(vals):
    """DerSimonian-Laird random effects. vals = [(delta, se)]"""
    k = len(vals)
    if k < 2: return None
    w = [1 / s ** 2 for _, s in vals]
    fe = sum(wi * d for wi, (d, _) in zip(w, vals)) / sum(w)
    Q = sum(wi * (d - fe) ** 2 for wi, (d, _) in zip(w, vals))
    C = sum(w) - sum(wi ** 2 for wi in w) / sum(w)
    tau2 = max(0.0, (Q - (k - 1)) / C) if C > 0 else 0.0
    ws = [1 / (s ** 2 + tau2) for _, s in vals]
    re = sum(wi * d for wi, (d, _) in zip(ws, vals)) / sum(ws)
    se_re = math.sqrt(1 / sum(ws))
    I2 = max(0.0, (Q - (k - 1)) / Q) if Q > 0 else 0.0
    return dict(k=k, re=re, se=se_re, tau=math.sqrt(tau2), I2=I2, Q=Q)

all_comps = sorted({x for c in camp.values() for x in c["deltas"]}, key=lambda x: (n_alloc(x), x))
A1_rows = []; pooled = {}
for mach, reg in (("M1", "CPU"), ("M1", "MEM"), ("M2", "CPU"), ("M2", "MEM")):
    ids = [cid for cid, c in camp.items() if c["machine"] == mach and c["regime"] == reg and c["status"] in POOLABLE]
    for comp in all_comps:
        vals = [(camp[i]["deltas"][comp][0], se_cache[i][comp], i) for i in ids if comp in camp[i]["deltas"]]
        if not vals: continue
        ds = [v[0] for v in vals]
        pr = dl_pool([(d, s) for d, s, _ in vals])
        rec = [v for v in vals if camp[v[2]]["status"] == "record"]
        pooled[(mach, reg, comp)] = dict(vals=vals, pool=pr, median=st.median(ds), rec=rec[0][0] if rec else None)
        A1_rows.append([mach, reg, comp, n_alloc(comp), len(vals),
                        "%+.1f" % (rec[0][0] * 100) if rec else "",
                        "%+.1f" % (st.median(ds) * 100), "%+.1f" % (min(ds) * 100), "%+.1f" % (max(ds) * 100),
                        "%+.1f" % (pr["re"] * 100) if pr else "", "%.1f" % (2 * pr["se"] * 100) if pr else "",
                        "%.1f" % (pr["tau"] * 100) if pr else "", "%.0f" % (pr["I2"] * 100) if pr else "",
                        " ".join("%s=%+.1f" % (i, d * 100) for d, _, i in vals)])
write_csv("A1_inter_campagnes.csv",
          ["machine", "regime", "composition", "n_alloc", "n_campaigns", "delta_record", "median", "min", "max",
           "pooled_RE", "2SE_pooled", "tau_between", "I2_pct", "per_campaign"], A1_rows)

# =====================================================================================
# A2 -- blocked vs independent bootstrap on the record campaigns ; A4 dagger audit
# =====================================================================================
B_FULL = 20000
A2_rows, A4_rows = [], []
blocked = {}
for cid in ("M1-CPU-rec", "M1-MEM-rec", "M2-CPU-rec", "M2-MEM-rec"):
    c = camp[cid]; comps = sorted(c["deltas"])
    bb, nrep = boot_blocked(c["R"], comps, B_FULL, 42)
    lab = {"M1-CPU-rec": "M1-CPU", "M1-MEM-rec": "M1-MEM", "M2-CPU-rec": "M2-CPU", "M2-MEM-rec": "M2-MEM"}[cid]
    pub = published[lab]
    blocked[cid] = {}
    for comp in comps:
        d = c["deltas"][comp][0]
        sb = sorted(bb[comp]); se_b = st.stdev(sb)
        lo_b, hi_b = pct(sb, ALPHA / 2), pct(sb, 1 - ALPHA / 2)
        p = pub[comp]
        z_i, z_b = p["z"], (d / se_b if se_b > 0 else 0)
        sig_i, sig_b = p["significant"], abs(d) > Z * se_b
        ci_i, ci_b = p["sig_by_ci"], not (lo_b <= 0 <= hi_b)
        blocked[cid][comp] = dict(se=se_b, z=z_b, sig=sig_b, sigci=ci_b)
        A2_rows.append([lab, comp, "%+.1f" % (d * 100), "%.1f" % (p["se"] * 200), "%.1f" % (se_b * 200),
                        "%.2f" % (se_b / p["se"]), "%.2f" % z_i, "%.2f" % z_b, int(sig_i), int(sig_b), int(ci_i), int(ci_b)])
        # A4: dagger status under the published (independent) bootstrap
        if sig_i and not ci_i: status = "dagger (z-sig, CI straddles 0)"
        elif sig_i and ci_i: status = "* (both criteria)"
        elif (not sig_i) and ci_i: status = "CI-only (not z-sig)"
        else: status = "n.s."
        if 3.0 <= abs(z_i) <= 3.5 or (sig_i != ci_i):
            A4_rows.append([lab, comp, "%+.1f" % (d * 100), "%.2f" % z_i,
                            "[%+.1f, %+.1f]" % (p["ci_lo"] * 100, p["ci_hi"] * 100), status,
                            "%.2f" % z_b, "[%+.1f, %+.1f]" % (lo_b * 100, hi_b * 100),
                            "*" if (sig_b and ci_b) else ("dagger" if sig_b else ("CI-only" if ci_b else "n.s."))])
write_csv("A2_bootstrap_independant_vs_bloque.csv",
          ["campaign", "composition", "delta", "2SE_indep", "2SE_blocked", "SE_ratio_b/i", "z_indep", "z_blocked",
           "sig_z_indep", "sig_z_blocked", "sig_CI_indep", "sig_CI_blocked"], A2_rows)
write_csv("A4_audit_dagger.csv",
          ["campaign", "composition", "delta", "z_indep", "CI_Bonferroni_indep", "status_published_rule",
           "z_blocked", "CI_Bonferroni_blocked", "status_blocked"], A4_rows)

# =====================================================================================
# A3 -- both normalisations
# =====================================================================================
A3_rows = []
for cid in ("M1-CPU-rec", "M1-MEM-rec", "M2-CPU-rec", "M2-MEM-rec"):
    for comp, (d, add, rc) in sorted(camp[cid]["deltas"].items(), key=lambda kv: -kv[1][0]):
        A3_rows.append([cid.replace("-rec", ""), comp, n_alloc(comp), "%.3f" % rc, "%.3f" % add,
                        "%+.1f" % (d * 100), "%+.1f" % (100 * d / add)])
write_csv("A3_double_normalisation.csv",
          ["campaign", "composition", "n_alloc", "rho_C", "rho_additive", "delta_pts_baseline", "delta_pct_of_additive"], A3_rows)

# LaTeX appendix: all 26 compositions, 4 record campaigns, both normalisations
tex = [r"\begin{table*}[t]", r"\caption{All 26 compositions. For each campaign of record: $\delta$ in points of baseline energy and, in parentheses, as a percentage of the additive prediction $\rho_{\text{additive}}$. $^{\ast}$ significant under both the $z$-rule and the Bonferroni-level percentile interval; $^{\dagger}$ significant under the $z$-rule only.}",
       r"\label{tab:appendix_all}", r"\centering\scriptsize", r"\begin{tabular}{lcrrrr}", r"\toprule",
       r"\textbf{Composition} & \textbf{alloc.} & \textbf{M1 CPU} & \textbf{M2 CPU} & \textbf{M1 MEM} & \textbf{M2 MEM}\\", r"\midrule"]
order = ("M1-CPU", "M2-CPU", "M1-MEM", "M2-MEM")
for comp in sorted(published["M1-CPU"], key=lambda x: (-n_alloc(x), -published["M1-CPU"][x]["delta"])):
    cells = []
    for lab in order:
        p = published[lab][comp]
        mark = r"^{\ast}" if (p["significant"] and p["sig_by_ci"]) else (r"^{\dagger}" if p["significant"] else "")
        cells.append(r"$%+.1f%s$ {\tiny(%+.1f)}" % (p["delta"] * 100, mark, 100 * p["delta"] / p["additive"]))
    tex.append(r"\texttt{%s} & %d & %s\\" % (comp, n_alloc(comp), " & ".join(cells)))
tex += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
open(os.path.join(OUT, "tab_annexe_26_compositions.tex"), "w").write("\n".join(tex) + "\n")

# =====================================================================================
# A5 -- dose-response with intervals
# =====================================================================================
A5_rows = []
B_DR = 2000
for cid in ("M1-CPU-rec", "M2-CPU-rec", "M1-MEM-rec", "M2-MEM-rec"):
    c = camp[cid]; comps = sorted(c["deltas"])
    groups = {g: [x for x in comps if n_alloc(x) == g] for g in range(4)}
    bb, _ = boot_blocked(c["R"], comps, B_DR, 11)
    meds = {g: [] for g in groups}; superlin = 0
    for i in range(B_DR):
        m = {g: (st.median([bb[x][i] for x in groups[g]]) if groups[g] else None) for g in groups}
        for g in groups:
            if m[g] is not None: meds[g].append(m[g])
        if None not in (m[1], m[2], m[3]) and (m[3] - m[2]) > (m[2] - m[1]): superlin += 1
    for g in range(4):
        if not groups[g]: continue
        pt = st.median([c["deltas"][x][0] for x in groups[g]]); s = sorted(meds[g])
        A5_rows.append([cid.replace("-rec", ""), g, len(groups[g]), " ".join(groups[g]),
                        "%+.1f" % (pt * 100), "[%+.1f, %+.1f]" % (pct(s, .025) * 100, pct(s, .975) * 100),
                        "%.2f" % (superlin / B_DR) if g == 3 else ""])
write_csv("A5_dose_reponse.csv", ["campaign", "n_alloc", "n_comp", "compositions", "median_delta", "CI95_measurement",
                                   "P(super-linear) [g=3 row]"], A5_rows)

# =====================================================================================
# A6 -- campaign inventory
# =====================================================================================
A6_rows = []
for cid, mach, reg, fn, filt, status, K, date, note in CAMPAIGNS:
    if cid not in camp: continue
    c = camp[cid]
    A6_rows.append([cid, mach, reg, fn, status, date, int(c["n_reps"]), c["n_cfg"], K, "yes" if c["has_time"] else "no", note])
for fn, note in (("M1_perf_cpu.csv", "perf counters, 13 configs, K = 5000 (+100 warm-up)"),
                 ("M1_dispatch_perf.csv", "perf counters, dispatch v1, K = 5000 (+100)"),
                 ("M1_dispatch_perf_v2.csv", "perf counters, dispatch v2, K = 5000 (+100)"),
                 ("M1_gcpause_cpu.csv", "GC pause, matrixk K = 2000, 10 passes"),
                 ("M1_gcpause_mem.csv", "GC pause, matrixk K = 2000, 10 passes"),
                 ("M1_alloc_cpu.csv", "allocation counters, matrixk"), ("M1_alloc_mem.csv", "allocation counters, matrixk")):
    A6_rows.append(["-", "M1", "", fn, "auxiliary", "oct. (à confirmer)", "", "", "", "", note])
A6_rows.append(["-", "M1", "MEM", "(missing)", "MISSING", "?", "", "", 1000, "",
                "memory-bound amplification data behind Figure 2 is not in data_campaigns/"])
write_csv("A6_inventaire_campagnes.csv", ["id", "machine", "regime", "file", "status", "measured", "reps",
                                          "configs", "K", "time_captured", "note"], A6_rows)

# =====================================================================================
# A7 -- energy vs time
# =====================================================================================
def keyd(r): return r["config"] + ("x%s" % r["dup"] if r.get("dup", "1") != "1" else "")
A7_rows = []; a7_points = []
time_sets = [("M1-CPU-ET", "M1_cpu_ET.csv", None), ("M1-MEM-ET", "M1_mem_ET.csv", None),
             ("M1-CPU-amp1x", "M1_amp_cpu_1x.csv", None), ("M1-CPU-amp5x", "M1_amp_cpu_5x.csv", None),
             ("M1-CPU-disp2(all dup)", "M1_dispatch_energy_v2.csv", "dup")]
for w in (1, 2, 4, 8, 16, 32):
    time_sets.append(("M1-CPU-sweep2-w%d" % w, "M1_sweep_cpu_v2.csv", w))
for lab, fn, mode in time_sets:
    def ld(num, den):
        R = {}
        for row in csv.DictReader(open(os.path.join(DATA, fn))):
            if isinstance(mode, int) and row.get("kernel_rep") != str(mode): continue
            a, b = fnum(row[num]), fnum(row[den])
            if a is None or not b: continue
            k = keyd(row) if mode == "dup" else row["config"]
            R.setdefault(k, []).append(a / b)
        return {k: st.median(v) for k, v in R.items()}
    rE, rT = ld("e_cfg", "e_base"), ld("t_cfg", "t_base")
    pts = []
    for k in rE:
        base = k.split("x")[0]; mult = int(k.split("x")[1]) if "x" in k else 1
        parts = dec(base) * mult if mult > 1 else dec(base)
        if len(parts) < 2 or not all(p in rE for p in parts): continue
        dE = rE[k] - (1 + sum(rE[p] - 1 for p in parts)); dT = rT[k] - (1 + sum(rT[p] - 1 for p in parts))
        pts.append((k, dE, dT))
    if len(pts) < 3: continue
    xs = [p[2] for p in pts]; ys = [p[1] for p in pts]
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys); sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    r = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")
    slope = sxy / sxx if sxx > 0 else float("nan")
    ratios = [y / x for _, y, x in pts if abs(x) > 0.02]
    A7_rows.append([lab, len(pts), "%.3f" % r, "%.2f" % slope,
                    "%.2f" % min(ratios) if ratios else "", "%.2f" % max(ratios) if ratios else "",
                    "%.2f" % st.median(ratios) if ratios else ""])
    for k, dE, dT in pts: a7_points.append([lab, k, "%+.1f" % (dE * 100), "%+.1f" % (dT * 100)])
write_csv("A7_energie_vs_temps.csv", ["campaign", "n_comp", "pearson_r", "slope_dE_on_dT", "min_dE/dT", "max_dE/dT", "median_dE/dT"], A7_rows)
write_csv("A7_points.csv", ["campaign", "composition", "delta_energy", "delta_time"], a7_points)

# =====================================================================================
# A8 -- instruction counts with the correct divisor (K + 100 warm-up tasks)
# =====================================================================================
def perf_surplus(fn, K, warm=100):
    D = {}
    for row in csv.DictReader(open(os.path.join(DATA, fn))):
        k = keyd(row) if "dup" in row else row["config"]
        v = fnum(row["instructions"])
        if v is not None: D.setdefault(k, []).append(v)
    M = {k: st.median(v) for k, v in D.items()}; b = M["base"]
    out = {}
    for k in M:
        if k == "base": continue
        base = k.split("x")[0]; mult = int(k.split("x")[1]) if "x" in k else 1
        parts = dec(base) * mult if mult > 1 else dec(base)
        if len(parts) < 2 or not all(p in M for p in parts): continue
        net = M[k] - b; pred = sum(M[p] - b for p in parts)
        out[k] = ((net - pred) / ((K + warm) * N_ITER), (net - pred) / (K * N_ITER), 100 * (net - pred) / pred)
    return out, b / ((K + warm) * N_ITER), b / (K * N_ITER)
A8_rows = []
for fn in ("M1_perf_cpu.csv", "M1_dispatch_perf.csv", "M1_dispatch_perf_v2.csv"):
    s, kc, kold = perf_surplus(fn, 5000)
    A8_rows.append([fn, "base kernel (upper bound, incl. start-up)", "%.2f" % kc, "%.2f" % kold, ""])
    for k, (new, old, pc) in sorted(s.items()):
        A8_rows.append([fn, k, "%.2f" % new, "%.2f" % old, "%+.1f" % pc])
write_csv("A8_instructions_par_iteration.csv", ["file", "configuration", "surplus_per_iter_K+100", "as_published_K", "surplus_pct_of_prediction"], A8_rows)
# two-term model refit on dispatch v2 with the corrected divisor
s2, kc2, _ = perf_surplus("M1_dispatch_perf_v2.csv", 5000)
mono2 = st.mean([s2[k][0] for k in ("Bux2", "Mex2", "Obx2")]); mono3 = st.mean([s2[k][0] for k in ("Bux3", "Mex3")])
poly2 = st.mean([s2[k][0] for k in ("BuMe", "ObMe")]); poly3 = s2["FaBuMe"][0]
# least squares on y = a(m-1) + b*m*poly over the 4 cells
cells = [(2, 0, mono2), (3, 0, mono3), (2, 1, poly2), (3, 1, poly3)]
X = [((m - 1), m * p) for m, p, _ in cells]; Y = [y for _, _, y in cells]
s11 = sum(x[0] ** 2 for x in X); s22 = sum(x[1] ** 2 for x in X); s12 = sum(x[0] * x[1] for x in X)
t1 = sum(x[0] * y for x, y in zip(X, Y)); t2 = sum(x[1] * y for x, y in zip(X, Y))
det = s11 * s22 - s12 ** 2; a = (t1 * s22 - t2 * s12) / det; bcoef = (s11 * t2 - s12 * t1) / det
resid = [y - (a * x0 + bcoef * x1) for (x0, x1), y in zip(X, Y)]
stdc = s2.get("StDeAd", (float("nan"),))[0]

# =====================================================================================
# A1b -- does significance replicate? record campaign vs its re-run (same machine, regime)
# A9  -- contraction factor CPU -> MEM, per matched pair of campaigns
# =====================================================================================
def sig_table(cid, B=4000, seed=5):
    c = camp[cid]; comps = sorted(c["deltas"])
    bs = boot_indep(c["R"], comps, B, seed); out = {}
    for k in comps:
        s = sorted(bs[k]); se = st.stdev(s); d = c["deltas"][k][0]
        lo, hi = pct(s, ALPHA / 2), pct(s, 1 - ALPHA / 2)
        out[k] = dict(d=d, z=abs(d) > Z * se, ci=not (lo <= 0 <= hi))
    return out
A1b_rows = []; A1b_summary = []
for rec, rep in (("M1-CPU-rec", "M1-CPU-ET"), ("M1-MEM-rec", "M1-MEM-ET")):
    ta, tb = sig_table(rec), sig_table(rep)
    common = sorted(set(ta) & set(tb))
    for k in common:
        A1b_rows.append([rec.replace("-rec", ""), k, n_alloc(k), "%+.1f" % (ta[k]["d"] * 100), int(ta[k]["z"]), int(ta[k]["z"] and ta[k]["ci"]),
                         "%+.1f" % (tb[k]["d"] * 100), int(tb[k]["z"]), int(tb[k]["z"] and tb[k]["ci"])])
    def both(t, k): return t[k]["z"] and t[k]["ci"]
    for rule, f in (("z-rule", lambda t, k: t[k]["z"]), ("z + percentile", both)):
        sa = [k for k in common if f(ta, k)]; sb = [k for k in common if f(tb, k)]
        rep_same = [k for k in sa if f(tb, k) and (ta[k]["d"] > 0) == (tb[k]["d"] > 0)]
        A1b_summary.append((rec.replace("-rec", ""), rule, len(sa), len(sb), len(rep_same), [k for k in sa if k not in rep_same]))
write_csv("A1b_replication_significance.csv", ["campaign", "composition", "n_alloc", "delta_record", "z_sig_record", "robust_sig_record",
                                               "delta_rerun", "z_sig_rerun", "robust_sig_rerun"], A1b_rows)

A9_rows = []
for cpu, mem, lab in (("M1-CPU-rec", "M1-MEM-rec", "M1 record"), ("M1-CPU-ET", "M1-MEM-ET", "M1 re-run (ET)"),
                      ("M2-CPU-rec", "M2-MEM-rec", "M2 record")):
    dc, dm = camp[cpu]["deltas"], camp[mem]["deltas"]
    al = [k for k in dc if n_alloc(k) >= 2 and k in dm]
    ratio_med = st.median([dc[k][0] for k in al]) / st.median([dm[k][0] for k in al])
    per = [dc[k][0] / dm[k][0] for k in al if dm[k][0] > 0.01]
    A9_rows.append([lab, len(al), "%+.1f" % (st.median([dc[k][0] for k in al]) * 100), "%+.1f" % (st.median([dm[k][0] for k in al]) * 100),
                    "%.1f" % ratio_med, "%.1f-%.1f" % (min(per), max(per)) if per else ""])
write_csv("A9_contraction_cpu_mem.csv", ["pair", "n_alloc_compositions", "median_delta_CPU", "median_delta_MEM",
                                          "ratio_of_medians", "per_composition_ratio_range"], A9_rows)

# =====================================================================================
# A10 -- did the baseline itself move between campaigns? (median baseline energy, signatures)
# =====================================================================================
A10_rows = []
for cid in ("M1-CPU-rec", "M1-CPU-ET", "M1-MEM-rec", "M1-MEM-ET", "M2-CPU-rec", "M2-MEM-rec"):
    fn = camp[cid]["file"]
    eb = [fnum(r["e_base"]) for r in csv.DictReader(open(os.path.join(DATA, fn))) if fnum(r["e_base"])]
    rho = camp[cid]["rho"]
    A10_rows.append([cid, "%.2f" % st.median(eb)] + ["%.3f" % rho[p] for p in PATTERNS])
write_csv("A10_baseline_et_signatures.csv", ["campaign", "median_e_base_J"] + ["rho_" + p for p in PATTERNS], A10_rows)

# =====================================================================================
# report
# =====================================================================================
P("# Rapport de la phase A — ré-analyse des campagnes existantes")
P("Généré par `analyse_phaseA.py` (aucune nouvelle mesure). Les valeurs publiées sont d'abord")
P("reproduites à l'identique (contrôle : FaBuMe M1-CPU = %+.1f %%)." % (chk["delta"] * 100))

H("## A1 — Variabilité inter-campagnes et estimation poolée")
P("Pooling à effets aléatoires (DerSimonian–Laird) sur les campagnes verrouillées ; τ = écart-type")
P("**entre campagnes**, I² = part de la variance totale due à l'hétérogénéité entre campagnes.")
P("")
P("| machine/régime | composition | n camp. | Tableau 2 | médiane | plage | poolé ± 2SE | τ | I² |")
P("|---|---|---|---|---|---|---|---|---|")
for (mach, reg, comp), v in pooled.items():
    if len(v["vals"]) < 2: continue
    ds = [x[0] for x in v["vals"]]; pr = v["pool"]
    P("| %s %s | %s | %d | %s | %+.1f | %+.1f à %+.1f | %+.1f ± %.1f | %.1f | %.0f %% |" % (
        mach, reg, comp, len(ds), ("%+.1f" % (v["rec"] * 100)) if v["rec"] is not None else "—",
        st.median(ds) * 100, min(ds) * 100, max(ds) * 100, pr["re"] * 100, 2 * pr["se"] * 100, pr["tau"] * 100, pr["I2"] * 100))
P("")
P("Compositions n'ayant qu'une campagne (M2, et une partie de M1) : la valeur du Tableau 2 est")
P("mono-campagne ; sa variance inter-campagnes est inconnue.")

H("## A1b — La significativité se réplique-t-elle ? (campagne de référence vs re-run)")
P("| campagne | règle | signif. référence | signif. re-run | répliquées (même signe) | non répliquées |")
P("|---|---|---|---|---|---|")
for lab, rule, na, nb, nr, miss in A1b_summary:
    P("| %s | %s | %d | %d | %d | %s |" % (lab, rule, na, nb, nr, ", ".join(miss) if miss else "—"))

H("## A9 — Facteur de contraction calcul → mémoire, par paire de campagnes")
P("Définition : médiane de δ des compositions à ≥ 2 allouants en calcul / même médiane en mémoire.")
P("")
P("| paire | n | médiane δ calcul | médiane δ mémoire | rapport des médianes | plage par composition |")
P("|---|---|---|---|---|---|")
for r in A9_rows: P("| %s | %s | %s | %s | %s× | %s |" % tuple(r))

H("## A10 — La ligne de base elle-même a-t-elle bougé entre campagnes ?")
P("| campagne | énergie médiane de la baseline (J, K = 1000) | " + " | ".join("ρ " + p for p in PATTERNS) + " |")
P("|---|---|" + "---|" * len(PATTERNS))
for r in A10_rows: P("| " + " | ".join(r) + " |")

H("## A2 — Bootstrap par passe (bloqué) vs bootstrap indépendant (publié)")
for cid in ("M1-CPU-rec", "M1-MEM-rec", "M2-CPU-rec", "M2-MEM-rec"):
    rows = [r for r in A2_rows if r[0] == cid.replace("-rec", "")]
    ratios = [float(r[5]) for r in rows]
    nsi = sum(r[8] for r in rows); nsb = sum(r[9] for r in rows)
    changed = [r[1] for r in rows if r[8] != r[9]]
    P("- **%s** : SE bloqué / SE indépendant = médiane %.2f (min %.2f, max %.2f) ; significatives (règle z) %d → %d%s" % (
        cid.replace("-rec", ""), st.median(ratios), min(ratios), max(ratios), nsi, nsb,
        (" ; changent de statut : " + ", ".join(changed)) if changed else " ; aucun changement de statut"))

H("## A3 — Les deux normalisations de δ (campagnes de référence, compositions allouantes en tête)")
P("| campagne | composition | δ (points de baseline) | δ (% de la prédiction additive) |")
P("|---|---|---|---|")
for r in A3_rows:
    if r[1] in ("FaBuMe", "BuObMe", "BuMe", "BuOb", "FaBu", "ObMe", "StDeAd"):
        P("| %s | %s | %s | %s |" % (r[0], r[1], r[5], r[6]))

H("## A4 — Audit du marquage † (cas 3,0 ≤ |z| ≤ 3,5 ou critères en désaccord)")
P("Règle de l'article : `*` si |δ| > 3,098·SE **et** intervalle percentile au niveau Bonferroni")
P("excluant 0 ; `†` si seule la règle z est satisfaite.")
P("")
P("| campagne | composition | δ | z | IC Bonferroni (indép.) | statut publié | z bloqué | statut bloqué |")
P("|---|---|---|---|---|---|---|---|")
for r in A4_rows:
    P("| %s | %s | %s | %s | %s | %s | %s | %s |" % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[8]))

H("## A5 — Dose-réponse avec intervalles (bootstrap par passe)")
P("| campagne | n allouants | n comp. | médiane δ | IC 95 % (mesure) | P(super-linéaire) |")
P("|---|---|---|---|---|---|")
for r in A5_rows: P("| %s | %s | %s | %s | %s | %s |" % (r[0], r[1], r[2], r[4], r[5], r[6]))
P("")
P("Le groupe « 3 allouants » ne contient que FaBuMe et BuObMe ; les triplets mixtes StObMe et")
P("AdObMe sont dans le groupe « 2 allouants ». L'IC ne reflète que l'incertitude de mesure, pas la")
P("variabilité entre compositions possibles.")

H("## A6 — Inventaire des campagnes")
P("Voir `A6_inventaire_campagnes.csv`. Dates de mesure des campagnes d'octobre à confirmer ; les")
P("données d'amplification en régime mémoire (Figure 2) ne sont pas dans `data_campaigns/`.")

H("## A7 — Interaction en énergie vs en temps")
P("| campagne | n | r | pente δE/δT | δE/δT min | max | médiane |")
P("|---|---|---|---|---|---|---|")
for r in A7_rows: P("| %s | %s | %s | %s | %s | %s | %s |" % tuple(r))

H("## A8 — Instructions par itération avec le bon diviseur (K + 100)")
P("`runk` exécute 100 tâches d'échauffement que `perf` compte : le diviseur correct est")
P("(K + 100)·n, pas K·n. Les pourcentages ne changent pas ; les valeurs absolues baissent de 2 %.")
P("")
P("- noyau de référence : %.1f instr./itération au maximum (avant : 43,4 ; inclut le démarrage du runtime)" % kc2)
P("- mono m=2 : %.2f · mono m=3 : %.2f · poly m=2 : %.2f · poly m=3 : %.2f · StDeAd : %.2f" % (mono2, mono3, poly2, poly3, stdc))
P("- modèle à deux termes réajusté (moindres carrés sur 4 cellules, 2 paramètres) :")
P("  surplus(m) = **%.2f**·(m−1) + **%.2f**·m·1[polymorphe] ; résidus : %s" % (a, bcoef, ", ".join("%+.2f" % x for x in resid)))
P("  (avant : 3,1 et 11,3). 2 paramètres pour 4 cellules non triviales = 2 degrés de liberté.")

open(os.path.join(OUT, "RAPPORT_PHASE_A.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))
