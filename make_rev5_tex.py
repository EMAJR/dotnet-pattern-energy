# =====================================================================================
# Revision 5 -- writes every number and table of the article from the analysis outputs.
#   rev5/numbers.tex           \newcommand macros (letters only), one per value used in the text
#   rev5/tab_*.tex             complete table environments, included with \input{}
#   rev5/fig_regime_v4.pdf, rev5/fig_dose_response_v4.pdf
# Inputs: rev5/values.json, rev5/sig.json (analyse_rev5_main.py) and data_campaigns/ (topology).
# Usage: python3 analyse_rev5_main.py && python3 make_rev5_tex.py
# =====================================================================================
import csv, os, json, math
import numpy as np
import statistics as st
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data_campaigns"); OUT = os.path.join(HERE, "rev5")
V = json.load(open(os.path.join(OUT, "values.json"))); SJ = json.load(open(os.path.join(OUT, "sig.json")))
SIG, SIGOLD, COMPS = SJ["SIG"], SJ["SIGOLD"], SJ["COMPS"]
ALLOC = {"Fa", "Bu", "Ob", "Me"}; Z = 3.0976; ALPHA = 0.05 / 26
CN = {"M1CPU": "MoneCpu", "M1MEM": "MoneMem", "M2CPU": "MtwoCpu", "M2MEM": "MtwoMem"}
MN = {"M1": "Mone", "M2": "Mtwo"}
def dec(c): return [c[i:i + 2] for i in range(0, len(c), 2)]
def nalloc(c): return sum(p in ALLOC for p in dec(c))
def sg(x, nd=1): return f"{x:+.{nd}f}"
def us(x, nd=1): return f"{x:.{nd}f}"
MAC = {}
def m(name, val):
    assert name.isalpha(), name
    assert name not in MAC or MAC[name] == val, (name, MAC[name], val)
    MAC[name] = val
def star(s): return {"*": "^{\\ast}", "dag": "^{\\circ}", "": ""}[s]

# ---------------------------------------------------------------- matrices
for k, c4 in CN.items():
    S = SIG[k]
    for c in COMPS:
        m(f"d{c}{c4}", sg(S[c]["d"])); m(f"tse{c}{c4}", us(S[c]["two"]))
    m(f"nSup{c4}", str(V[k]["nsup"])); m(f"nSub{c4}", str(V[k]["nsub"])); m(f"nDag{c4}", str(V[k]["ndag"]))
    m(f"nSig{c4}", str(V[k]["nsup"] + V[k]["nsub"]))
    m(f"Ezero{c4}", us(V[k]["E0"], 2)); m(f"tzero{c4}", us(V[k]["t0"], 2))
    m(f"passRatio{c4}", us(V[k]["passratio"], 2))
pr = [V[k]["passratio"] for k in CN]; m("passRatioLo", us(min(pr), 2)); m("passRatioHi", us(max(pr), 2))
m("nSubTotal", str(sum(V[k]["nsub"] for k in CN)))
for k, c4 in CN.items():
    for p in ["St", "De", "Ad", "Fa", "Bu", "Ob", "Me"]: m(f"sig{p}{c4}", us(V["sig"][k][p], 3))
# signatures in % for the text
for k, c4 in CN.items():
    for p in ["St", "Ad", "Bu"]: m(f"sigPct{p}{c4}", us(100 * (V["sig"][k][p] - 1)))

# ---------------------------------------------------------------- pooling
for key, P in V["pool"].items():
    mach, c = key.split("_"); nm = f"{c}{MN[mach]}"
    m(f"pool{nm}", sg(100 * P["reml"])); m(f"poolLo{nm}", sg(100 * P["lo"])); m(f"poolHi{nm}", sg(100 * P["hi"]))
    m(f"poolTau{nm}", us(100 * P["tau"])); m(f"poolQ{nm}", us(P["Q"])); m(f"poolDf{nm}", str(P["k"] - 1))
    m(f"poolP{nm}", us(P["p"], 2)); m(f"poolIsq{nm}", us(100 * P["I2"], 0)); m(f"poolK{nm}", str(P["k"]))
    m(f"poolDl{nm}", sg(100 * P["dl"])); m(f"poolDlTwo{nm}", us(200 * P["dlse"]))
    vals = [d for _, d, _ in P["values"]]; m(f"poolMin{nm}", sg(min(vals))); m(f"poolMax{nm}", sg(max(vals)))
    if P["loo_lo"] is not None: m(f"poolLooLo{nm}", sg(100 * P["loo_lo"])); m(f"poolLooHi{nm}", sg(100 * P["loo_hi"]))
for c, (a, b) in V["disp_shift"].items(): m(f"dispOne{c}", sg(a)); m(f"dispTwo{c}", sg(b))

# ---------------------------------------------------------------- kernel
VN = {"old": "Prev", "new": "Cur"}
for key, row in V["kernel"].items():
    mach, reg = key[:2], key[2:]; base = f"{MN[mach]}{reg.capitalize()}"
    for ver in ("old", "new"):
        r = row[ver]; nm = f"{base}{VN[ver]}"
        m(f"kE{nm}", us(r["E0"], 2)); m(f"kT{nm}", us(r["t0"], 2)); m(f"kInstr{nm}", us(r["instr"]))
        for c in ["FaBuMe", "BuMe", "BuObMe", "StDeAd"]: m(f"k{c}{nm}", sg(r[c][0]))
    for c in ["FaBuMe", "BuMe", "BuObMe", "StDeAd"]: m(f"kZ{c}{base}", us(abs(row[c + "_z"])))
    m(f"kTimeFactor{base}", us(row["old"]["t0"] / row["new"]["t0"], 2))
    m(f"kEnergyChange{base}", sg(100 * (row["new"]["E0"] / row["old"]["E0"] - 1), 0))
m("kShift", us(V["kernel"]["M1CPU"]["old"]["FaBuMe"][0] - V["kernel"]["M1CPU"]["new"]["FaBuMe"][0]))
m("kExtraInstrCpu", us(V["kernel"]["M1CPU"]["new"]["instr"] - V["kernel"]["M1CPU"]["old"]["instr"], 0))
m("kExtraInstrMem", us(V["kernel"]["M1MEM"]["new"]["instr"] - V["kernel"]["M1MEM"]["old"]["instr"], 0))

# ---------------------------------------------------------------- decomposition
for key, r in V["decomp"].items():
    k, c = key.split("_"); nm = f"{c}{CN[k]}"
    m(f"dE{nm}", sg(r["tot"])); m(f"dEW{nm}", sg(r["work"])); m(f"dEC{nm}", sg(r["cost"])); m(f"dEP{nm}", sg(r["power"]))
    m(f"ezeroNJ{CN[k]}", us(r["E0"]))
for mach in ("M1", "M2"):
    a, b = V["decomp"][f"{mach}CPU_FaBuMe"], V["decomp"][f"{mach}MEM_FaBuMe"]
    m(f"dilPoints{MN[mach]}", us(a["delta"] / b["delta"], 1)); m(f"dilBase{MN[mach]}", us(b["E0"] / a["E0"], 1))
    m(f"dilAbs{MN[mach]}", us(a["tot"] / b["tot"], 2))
CASES = V["cases"]

# ---------------------------------------------------------------- dose-response and allocation
for k, c4 in CN.items():
    d = V["dose"][k]
    for g, w in zip("0123", ["Zero", "One", "Two", "Three"]):
        m(f"dose{w}{c4}", sg(d["point"][g])); m(f"doseLo{w}{c4}", sg(d["ci"][g][0])); m(f"doseHi{w}{c4}", sg(d["ci"][g][1]))
    m(f"doseP{c4}", us(d["psl"], 2))
    a = V["alloc"][k]
    m(f"rVol{c4}", sg(a["r_vol"], 2)); m(f"rSrc{c4}", sg(a["r_src"], 2))
    m(f"bigLo{c4}", sg(a["big"][1])); m(f"bigHi{c4}", sg(a["big"][2])); m(f"smallLo{c4}", sg(a["small"][1])); m(f"smallHi{c4}", sg(a["small"][2]))
m("doseStepOneTwoMoneCpu", sg(V["dose"]["M1CPU"]["point"]["2"] - V["dose"]["M1CPU"]["point"]["1"]))
m("doseStepTwoThreeMoneCpu", sg(V["dose"]["M1CPU"]["point"]["3"] - V["dose"]["M1CPU"]["point"]["2"]))
rs = [V["alloc"][k]["r_src"] for k in CN]; rv = [V["alloc"][k]["r_vol"] for k in CN]
m("rSrcLo", sg(min(rs), 2)); m("rSrcHi", sg(max(rs), 2)); m("rVolLo", sg(min(rv), 2)); m("rVolHi", sg(max(rv), 2))

# ---------------------------------------------------------------- topology (shared vs dedicated sites)
rng = np.random.default_rng(5)
def load_topo(path, topo):
    R = {}
    for r in csv.DictReader(open(os.path.join(D, path))):
        if r["topo"] == topo: R.setdefault(r["config"], []).append(float(r["e_cfg"]) / float(r["e_base"]))
    return {c: np.array(v) for c, v in R.items()}
def dl(R, c, idx=None):
    md_ = (lambda a: np.median(a[rng.integers(0, len(a), (idx, len(a)))], axis=1)) if idx else np.median
    return md_(R[c]) - 1 - sum(md_(R[p]) - 1 for p in dec(c))
def tsig(R, c, B=20000):
    d = dl(R, c); bs = dl(R, c, B); se = bs.std(ddof=1); lo, hi = np.quantile(bs, [ALPHA / 2, 1 - ALPHA / 2])
    zr = abs(d) > Z * se; pr = lo > 0 or hi < 0
    return 100 * d, 200 * se, ("*" if zr and pr else ("dag" if zr else "")), bs
def instr_topo(path, topo, cfgs):
    R = [r for r in csv.DictReader(open(os.path.join(D, path))) if r["topo"] == topo]
    g = lambda c: (st.median(float(r["instructions"]) for r in R if r["config"] == c) - 0.49e9) / ((float(R[0]["K"]) + float(R[0]["warmup"])) * 200000)
    I = {c: g(c) for c in cfgs + ["base"] + sorted({p for x in cfgs for p in dec(x)})}
    return {c: I[c] - I["base"] - sum(I[p] - I["base"] for p in dec(c)) for c in cfgs}
TOPOC = ["FaBu", "BuMe", "BuOb", "ObMe", "FaBuMe", "BuObMe", "StDeAd"]
TOPO = {}
for lab, fe, fp in [("Mone", "phaseB/B4_energy.csv", "phaseB/B4_perf.csv"), ("MoneB", "phaseB/B4_energy_rep2.csv", "phaseB/B4_perf_rep2.csv"),
                    ("Mtwo", "M2_results_20261019/M2_B4_energy.csv", "M2_results_20261019/M2_B4_perf.csv"),
                    ("MtwoB", "M2b_results_20261020/M2b_B4_energy.csv", "M2b_results_20261020/M2b_B4_perf.csv")]:
    R0, R1, R2 = load_topo(fe, "0"), load_topo(fe, "1"), load_topo(fe, "2")
    i0, i1 = instr_topo(fp, "0", TOPOC), instr_topo(fp, "1", TOPOC)
    TOPO[lab] = {}
    for c in TOPOC:
        a, b, d2 = tsig(R0, c), tsig(R1, c), tsig(R2, c)
        diff = a[0] - b[0]; se = (a[3] - b[3]).std(ddof=1) * 100
        TOPO[lab][c] = dict(sh=a, de=b, di=d2, diff=diff, z=diff / se, ish=i0[c], ide=i1[c])
    ctl = TOPO[lab]["StDeAd"]["diff"]
    for c in TOPOC: TOPO[lab][c]["dd"] = TOPO[lab][c]["diff"] - ctl
def rng_(lab, key, cs=TOPOC[:-1]):
    v = [TOPO[lab][c][key] if not isinstance(TOPO[lab][c][key], tuple) else TOPO[lab][c][key][0] for c in cs]
    return min(v), max(v)
for lab in TOPO:
    lo, hi = rng_(lab, "diff"); m(f"topoDiffLo{lab.replace('B','b')}", sg(lo, 0)); m(f"topoDiffHi{lab.replace('B','b')}", sg(hi, 0))
    lo, hi = rng_(lab, "de"); m(f"topoDedLo{lab.replace('B','b')}", sg(lo, 0)); m(f"topoDedHi{lab.replace('B','b')}", sg(hi, 0))
    lo, hi = rng_(lab, "dd"); m(f"topoDDLo{lab.replace('B','b')}", sg(lo, 0)); m(f"topoDDHi{lab.replace('B','b')}", sg(hi, 0))
    zs = [TOPO[lab][c]["z"] for c in TOPOC[:-1]]; m(f"topoZLo{lab.replace('B','b')}", us(min(zs), 1)); m(f"topoZHi{lab.replace('B','b')}", us(max(zs), 1))
    m(f"topoCtlSh{lab.replace('B','b')}", sg(TOPO[lab]["StDeAd"]["sh"][0])); m(f"topoCtlDe{lab.replace('B','b')}", sg(TOPO[lab]["StDeAd"]["de"][0]))
    lo, hi = rng_(lab, "sh"); m(f"topoShLo{lab.replace('B','b')}", sg(lo, 0)); m(f"topoShHi{lab.replace('B','b')}", sg(hi, 0))
    ins = [abs(TOPO[lab][c]["ide"]) for c in TOPOC]; m(f"topoInstrDedMax{lab.replace('B','b')}", us(max(ins), 1))
# M2 dedicated sites: number of significantly sub-additive compositions (both campaigns)
for lab in ("Mtwo", "MtwoB"):
    n = sum(1 for c in TOPOC[:-1] if TOPO[lab][c]["de"][2] == "*" and TOPO[lab][c]["de"][0] < 0)
    m(f"topoNsub{lab.replace('B','b')}", str(n))

# ---------------------------------------------------------------- tables
def w(name, s): open(os.path.join(OUT, name), "w").write(s)
CELLS = ["M1CPU", "M2CPU", "M1MEM", "M2MEM"]
def cell(k, c, nd=1):
    s = SIG[k][c]; return f"${sg(s['d'], nd)}{star(s['star'])}$ {{\\scriptsize[{s['two']:.1f}]}}"
# Table: isolated signatures
rows = "\n".join(f"{nm} (\\texttt{{{p}}}) & {typ} & " + " & ".join(f"{V['sig'][k][p]:.3f}" for k in CELLS) + "\\\\"
                 + ("\n\\midrule" if p == "Ad" else "")
                 for p, nm, typ in [("St", "Strategy", "indirection"), ("De", "Decorator", "indirection"), ("Ad", "Adapter", "indirection"),
                                    ("Fa", "Factory", "allocating"), ("Bu", "Builder", "allocating"), ("Ob", "Observer", "allocating"), ("Me", "Memento", "allocating")])
w("tab_signatures.tex", r"""\begin{table}[t]
\caption{Isolated energy signatures $\rho_p$ of the seven patterns (paired total-energy ratio against the reference baseline, median over 15 runs; current kernel code: Machine~1 matrix re-run, Machine~2 second matrix). These values feed the additive prediction $\rho_{\text{additive}}(C) = 1 + \sum_{p \in C}(\rho_p - 1)$.}
\label{tab:signatures}
\centering \small
\begin{tabular}{llcccc}
\toprule
& & \multicolumn{2}{c}{$W_{\text{CPU}}$} & \multicolumn{2}{c}{$W_{\text{MEM}}$}\\
\cmidrule(lr){3-4}\cmidrule(lr){5-6}
\textbf{Pattern} & \textbf{Type} & \textbf{M1} & \textbf{M2} & \textbf{M1} & \textbf{M2}\\
\midrule
""" + rows + r"""
\bottomrule
\end{tabular}
\end{table}
""")
# Table 2: main deltas
ALLOCROWS = ["FaBuMe", "BuObMe", "BuMe", "BuOb", "FaBu", "ObMe"]; MIXROWS = ["StFa", "StOb", "StMe", "StDe", "DeAd"]
def r2(c, lab=None): return f"{lab or chr(92)+'texttt{'+c+'}'} & " + " & ".join(cell(k, c) for k in CELLS) + "\\\\"
cnt = " & ".join(f"{V[k]['nsup']+V[k]['nsub']} ({V[k]['nsup']} pos.)" + (f" $+\\,{V[k]['ndag']}^{{\\circ}}$" if V[k]["ndag"] else "") for k in CELLS)
w("tab_results_delta.tex", r"""\begin{table}[t]
\caption{Interaction deltas ($\delta$, points of baseline energy) with bootstrap $2\cdot\mathrm{SE}$ in brackets, current kernel code (Machine~1: matrix re-run; Machine~2: second matrix; 15 repetitions each). $^{\ast}$: significant after Bonferroni correction ($\alpha = 0.05/26$) under both the $z$-rule and the Bonferroni-level percentile interval; $^{\circ}$: $z$-rule only. Pooled estimates over all campaigns with the current kernel code are in Table~\ref{tab:intercampaign}, values with the previous kernel code in Table~\ref{tab:kernel}, and all 26 compositions in Appendix~\ref{app:all}.}
\label{tab:results_delta}
\centering
\small
\begin{tabular}{lcccc}
\toprule
& \multicolumn{2}{c}{\textbf{Compute-bound ($W_{\text{CPU}}$)}} & \multicolumn{2}{c}{\textbf{Memory-access ($W_{\text{MEM}}$)}}\\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}
\textbf{Composition} & \textbf{M1} & \textbf{M2} & \textbf{M1} & \textbf{M2}\\
\midrule
\multicolumn{5}{l}{\emph{Heap-allocating compositions}}\\
""" + "\n".join(r2(c) for c in ALLOCROWS) + r"""
\midrule
\multicolumn{5}{l}{\emph{Mixed and pure-indirection compositions}}\\
""" + "\n".join(r2(c) for c in MIXROWS) + "\n" + r"\rowcolor{gray!12}" + r2("StDeAd", r"\texttt{StDeAd} \emph{(control)}") + r"""
\midrule
\textbf{Significant / 26} & """ + cnt + r"""\\
\bottomrule
\end{tabular}
\end{table}
""")
# Table 4: pooling
def prow(mach, c, lab):
    P = V["pool"][f"{mach}_{c}"]; vals = [d for _, d, _ in P["values"]]
    loo = f"{sg(100*P['loo_lo'])}$ to ${sg(100*P['loo_hi'])}"
    return (f"{lab} & {P['k']} & ${sg(min(vals))}$ to ${sg(max(vals))}$ & ${sg(100*P['reml'])}$ {{\\scriptsize$[{sg(100*P['lo'])}, {sg(100*P['hi'])}]$}} & "
            f"{100*P['tau']:.1f} & {P['Q']:.1f} ({P['k']-1}) & {100*P['I2']:.0f}\\% & ${loo}$\\\\")
POOLROWS = [("FaBuMe", r"\texttt{FaBuMe}"), ("BuObMe", r"\texttt{BuObMe}"), ("BuMe", r"\texttt{BuMe}"), ("ObMe", r"\texttt{ObMe}"), ("StDeAd", r"\texttt{StDeAd} \emph{(control)}")]
w("tab_intercampaign.tex", r"""\begin{table}[t]
\caption{Pooled interaction over every compute-bound campaign run with the current kernel code (inclusion rule in Section~\ref{subsec:statistical_analysis}). \emph{Pooled}: restricted-maximum-likelihood estimate with its modified Hartung--Knapp 95\% interval; $\hat\tau$: between-campaign standard deviation; $Q$ (degrees of freedom) and $I^2$: heterogeneity; \emph{Leave-one-out}: range of the pooled estimate when each campaign is removed in turn. Machine~1: matrix re-run, code A/B, two dispatch, two topology (shared site), two weight-sweep ($w = 1$) and one amplification ($1\times$) campaigns, depending on the composition; Machine~2: second matrix, code A/B and two topology campaigns. Campaigns have 8 to 20 repetitions. The two topology campaigns use a patched harness whose baseline retires $0.07$ more instructions per iteration; without them, the estimates are given in the text.}
\label{tab:intercampaign}
\centering\small
\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{%
\begin{tabular}{lrrrrrrr}
\toprule
\textbf{Composition} & $k$ & \textbf{Range} & \textbf{Pooled} & $\hat\tau$ & $Q$ (df) & $I^2$ & \textbf{Leave-one-out}\\
\midrule
\multicolumn{8}{l}{\emph{Machine~1}}\\
""" + "\n".join(prow("M1", c, l) for c, l in POOLROWS) + r"""
\midrule
\multicolumn{8}{l}{\emph{Machine~2}}\\
""" + "\n".join(prow("M2", c, l) for c, l in POOLROWS) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")
# Table: kernel-code sensitivity
def krow(key, lab):
    r = V["kernel"][key]
    f = lambda ver: (f"{r[ver]['E0']:.2f} & {r[ver]['t0']:.2f} & {r[ver]['instr']:.1f} & "
                     + " & ".join(f"${sg(r[ver][c][0])}$" for c in ["FaBuMe", "BuMe", "StDeAd"]))
    zz = " & ".join(f"{abs(r[c+'_z']):.1f}" for c in ["FaBuMe", "BuMe", "StDeAd"])
    return (f"\\multirow{{3}}{{*}}{{{lab}}} & previous & {f('old')}\\\\\n & current & {f('new')}\\\\\n"
            f" & $|z|$ & & & & {zz}\\\\")
w("tab_kernel.tex", r"""\begin{table}[t]
\caption{Sensitivity to the reference kernel code (same machine, same evening, the two versions interleaved run by run; 10 repetitions). The current version adds a loop-count field and a loop whose body never executes at $w = 1$; both versions produce identical checksums. $E_0$: baseline energy (J per 1000 tasks); $t_0$: baseline time (s); \emph{instr.}: retired instructions per kernel iteration of the baseline (process start-up removed); $\delta$ in points of the version's own baseline; $|z|$: difference between versions over its bootstrap standard error.}
\label{tab:kernel}
\centering\small
\begin{tabular}{llrrrrrr}
\toprule
& \textbf{Kernel} & $E_0$ & $t_0$ & \textbf{instr.} & \texttt{FaBuMe} & \texttt{BuMe} & \texttt{StDeAd}\\
\midrule
""" + krow("M1CPU", r"M1, $W_{\text{CPU}}$") + "\n\\midrule\n" + krow("M2CPU", r"M2, $W_{\text{CPU}}$") + "\n\\midrule\n"
  + krow("M1MEM", r"M1, $W_{\text{MEM}}$") + "\n\\midrule\n" + krow("M2MEM", r"M2, $W_{\text{MEM}}$") + r"""
\bottomrule
\end{tabular}
\end{table}
""")
# Table: decomposition (five situations)
LAB = {"dilution": "Regime", "kernel code": "Kernel code", "call-site topology": "Call-site topology",
       "baseline weight": "Baseline weight", "duplicated layers": "Duplicated layers", "JIT configuration": "JIT configuration"}
drows = []; last = None
for r in CASES:
    if r["case"] == "baseline weight" and "w = 1" in r["conf"]: continue
    head = LAB[r["case"]] if r["case"] != last else ""
    if r["case"] != last and last is not None: drows.append("\\midrule")
    last = r["case"]
    drows.append(f"{head} & {r['conf']} & ${sg(r['delta'])}$ & {r['E0']:.1f} & {r['dinstr']:.1f} & ${sg(r['tot'])}$ & ${sg(r['work'])}$ & ${sg(r['cost'])}$ & ${sg(r['power'])}$\\\\")
w("tab_decomposition.tex", r"""\begin{table*}[t]
\caption{Decomposition of the interaction in absolute energy (nJ per kernel iteration). $\Delta E_{\text{int}} = \delta \cdot E_0$ is split exactly into \emph{work}, the instruction surplus $\Delta I_{\text{int}}$ valued at the baseline's energy per instruction, and two \emph{context} terms: the change in time per instruction and the change in power of the configurations involved (two-factor logarithmic mean Divisia split of their energy per instruction). The three terms add up to $\Delta E_{\text{int}}$. FaBuMe unless stated otherwise; sources: Table~\ref{tab:results_delta} (regime), Table~\ref{tab:kernel} (kernel code), Table~\ref{tab:topology} (topology, Machine~2), the weight-sweep counter runs (baseline weight), Table~\ref{tab:dispatch} (duplicated layers) and Section~\ref{subsec:res_jit} (JIT configuration). Instruction counts come from the counter runs of the same binaries; they reproduce to within $0.1$ instruction per iteration across protocols.}
\label{tab:decomposition}
\centering\small
\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{%
\begin{tabular}{llrrrrrrr}
\toprule
& & $\delta$ & $E_0$ & $\Delta I_{\text{int}}$ & $\Delta E_{\text{int}}$ & \textbf{Work} & \textbf{Time per} & \textbf{Power}\\
\textbf{Situation} & \textbf{Configuration} & (points) & (nJ) & (instr.) & (nJ) & (nJ) & \textbf{instr.} (nJ) & (nJ)\\
\midrule
""" + "\n".join(drows) + r"""
\bottomrule
\end{tabular}}
\end{table*}
""")
for r in CASES:
    key = {"dilution": "Dil", "kernel code": "Ker", "call-site topology": "Topo", "baseline weight": "Wt",
           "duplicated layers": "Dup", "JIT configuration": "Jit"}[r["case"]]
    tag = {"M1, $W_{\\mathrm{CPU}}$": "Cpu", "M1, $W_{\\mathrm{MEM}}$": "Mem", "M1, previous kernel": "Prev", "M1, current kernel": "Cur",
           "M2, shared site": "Shared", "M2, one site per layer": "Ded", "M1, \\texttt{Bu}$\\times 3$": "Bux", "M1, \\texttt{BuMe}": "BuMe",
           "M1, TC = 0 (measured)": "Measured", "M1, default .NET 8 configuration": "Default"}.get(r["conf"])
    if tag is None:
        tag = ("One" if "w = 1" in r["conf"] else "Eight") + ("Ctl" if "StDeAd" in r["conf"] else "")
    for f_, nm in (("delta", "d"), ("E0", "Ez"), ("tot", "T"), ("work", "W"), ("cost", "C"), ("power", "P"), ("dinstr", "I")):
        m(f"case{key}{tag}{nm}", (us if f_ in ("E0", "dinstr") else sg)(r[f_]))
# Table: topology (both machines, first campaign of each, with the contrast)
def tc(x): return f"${sg(x[0])}{star(x[2])}$ {{\\scriptsize[{x[1]:.1f}]}}"
trows = []
for c in TOPOC:
    a, b = TOPO["Mone"][c], TOPO["Mtwo"][c]
    lab = r"\texttt{StDeAd} \emph{(control)}" if c == "StDeAd" else f"\\texttt{{{c}}}"
    if c == "StDeAd": trows.append("\\midrule")
    trows.append(f"{lab} & {a['ish']:.1f} & {tc(a['sh'])} & {tc(a['de'])} & ${sg(a['diff'])}$ & {tc(b['sh'])} & {tc(b['de'])} & ${sg(b['diff'])}$\\\\")
w("tab_topology.tex", r"""\begin{table*}[t]
\caption{Invocation-topology manipulation ($W_{\text{CPU}}$, 8 repetitions, first campaign on each machine). The same allocating layers are invoked through one shared interface call site or through one interface call site per layer; each configuration is compared with the baseline of the same topology. $\delta$ in points of baseline energy with $2\cdot\mathrm{SE}$ in brackets ($^{\ast}$: both criteria of Section~\ref{subsec:statistical_analysis}; $^{\circ}$: $z$-rule only). \emph{instr.}: retired-instruction surplus per iteration at the shared site (Machine~1; Machine~2 identical to within $0.1$); through dedicated sites it is $0.0$ to $0.1$ on both machines. \emph{Contrast}: shared minus dedicated, the causal estimand. The direct-typed-call variant and the second campaign on each machine are reported in the text.}
\label{tab:topology}
\centering\small
\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{%
\begin{tabular}{lrrrrrrr}
\toprule
& & \multicolumn{3}{c}{\textbf{Machine~1}} & \multicolumn{3}{c}{\textbf{Machine~2}}\\
\cmidrule(lr){3-5}\cmidrule(lr){6-8}
\textbf{Composition} & \textbf{instr.} & \textbf{Shared} & \textbf{Per layer} & \textbf{Contrast} & \textbf{Shared} & \textbf{Per layer} & \textbf{Contrast}\\
\midrule
""" + "\n".join(trows) + r"""
\bottomrule
\end{tabular}}
\end{table*}
""")
# direct typed call (Machine 1, first campaign) for the text
dvals = [TOPO["Mone"][c]["di"] for c in TOPOC[:-1]]
m("topoDirLoMone", sg(min(x[0] for x in dvals), 0)); m("topoDirHiMone", sg(max(x[0] for x in dvals), 0))
m("topoDirNdagMone", str(sum(1 for x in dvals if x[2] == "dag")))
# Appendix: all 26
arows = []
for c in COMPS:
    cells = []
    for k in CELLS:
        s = SIG[k][c]; cells.append(f"${sg(s['d'])}{star(s['star'])}$")
    old = " & ".join(f"${sg(SIGOLD[k][c]['d'])}{star(SIGOLD[k][c]['star'])}$" for k in CELLS)
    arows.append(f"\\texttt{{{c}}} & {nalloc(c)} & " + " & ".join(cells) + " & " + old + "\\\\")
w("tab_annex.tex", r"""\begin{table}[H]
\caption{All 26 compositions: $\delta$ in points of baseline energy. Left: current kernel code (Table~\ref{tab:results_delta}). Right: the first campaigns of each machine, run with the previous kernel code (Section~\ref{subsec:res_kernel}). $^{\ast}$ significant under both the $z$-rule and the Bonferroni-level percentile interval; $^{\circ}$ $z$-rule only.}
\label{tab:appendix_all}
\centering\scriptsize
\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{%
\begin{tabular}{lcrrrrrrrr}
\toprule
& & \multicolumn{4}{c}{\textbf{Current kernel code}} & \multicolumn{4}{c}{\textbf{Previous kernel code (first campaigns)}}\\
\cmidrule(lr){3-6}\cmidrule(lr){7-10}
\textbf{Composition} & \textbf{alloc.} & \textbf{M1 CPU} & \textbf{M2 CPU} & \textbf{M1 MEM} & \textbf{M2 MEM} & \textbf{M1 CPU} & \textbf{M2 CPU} & \textbf{M1 MEM} & \textbf{M2 MEM}\\
\midrule
""" + "\n".join(arows) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")
# previous-kernel numbers used in the sensitivity section
for k, c4 in CN.items():
    for c in ["FaBuMe", "BuObMe", "StDeAd", "StFa"]: m(f"old{c}{c4}", sg(SIGOLD[k][c]["d"]))

# ---------------------------------------------------------------- ranges used in the text
for mach in ("M1", "M2"):
    r = [SIG[mach + "CPU"][c]["d"] / SIG[mach + "MEM"][c]["d"] for c in COMPS if nalloc(c) >= 2]
    m(f"contrLo{MN[mach]}", us(min(r))); m(f"contrHi{MN[mach]}", us(max(r)))
for k, c4 in CN.items():
    sub = [SIG[k][c]["d"] for c in COMPS if SIG[k][c]["star"] == "*" and SIG[k][c]["d"] < 0]
    if sub: m(f"subLo{c4}", sg(min(sub))); m(f"subHi{c4}", sg(max(sub)))
for k, c4 in CN.items():
    two = [SIG[k][c]["d"] for c in COMPS if nalloc(c) >= 2]; m(f"allocTwoLo{c4}", sg(min(two))); m(f"allocTwoHi{c4}", sg(max(two)))
m("ratioPoolTriplesCtlLo", us(min(V["pool"]["M2_FaBuMe"]["reml"], V["pool"]["M2_BuObMe"]["reml"]) / V["pool"]["M2_StDeAd"]["reml"]))
m("ratioPoolTriplesCtlHi", us(max(V["pool"]["M2_FaBuMe"]["reml"], V["pool"]["M2_BuObMe"]["reml"]) / V["pool"]["M2_StDeAd"]["reml"]))

# ---------------------------------------------------------------- revision 6 values
R6 = json.load(open(os.path.join(OUT, "values_rev6.json")))
pc = R6["percall"]
cpu = [v["pc"][0] for k, v in pc.items() if "CPU" in k]; mem = [v["pc"][0] for k, v in pc.items() if "MEM" in k]
nsc = [v["ns"] for k, v in pc.items() if "CPU" in k]
m("pcCpuLo", us(min(cpu))); m("pcCpuHi", us(max(cpu))); m("pcMemLo", us(min(mem))); m("pcMemHi", us(max(mem)))
m("nsCpuLo", us(min(nsc))); m("nsCpuHi", us(max(nsc)))
m("pcFaBuMeMoneCpu", us(pc["M1CPU_FaBuMe"]["pc"][0])); m("pcFaBuMeMtwoCpu", us(pc["M2CPU_FaBuMe"]["pc"][0]))
for mach in ("M1", "M2"):
    d = R6["dil"][mach]; m(f"dilAbsLo{MN[mach]}", us(d[1], 2)); m(f"dilAbsHi{MN[mach]}", us(d[2], 2))
for mach in ("M1", "M2"):
    P = R6["pool_same"][mach]; nm = MN[mach]
    m(f"poolSame{nm}", sg(100 * P["reml"])); m(f"poolSameLo{nm}", sg(100 * P["lo"])); m(f"poolSameHi{nm}", sg(100 * P["hi"])); m(f"poolSameK{nm}", str(P["k"]))
m("topoTimeLo", sg(R6["topo_time_range"][0], 0)); m("topoTimeHi", sg(R6["topo_time_range"][1], 0))
tri = [TOPO[l][c]["diff"] for l in TOPO for c in ("FaBuMe", "BuObMe")]
ks = V["kernel"]["M1CPU"]["old"]["FaBuMe"][0] - V["kernel"]["M1CPU"]["new"]["FaBuMe"][0]
m("triContrLo", us(min(tri) / ks)); m("triContrHi", us(max(tri) / ks))
CS = {r["tag"]: r for r in R6["cases"]}
for tag, r in CS.items():
    for f_, nm in (("tot", "T"), ("w_base", "W"), ("w_conf", "Wc"), ("w_shap", "Ws"), ("time", "C"), ("power", "P")):
        m(f"rsix{tag}{nm}", sg(r[f_][0])); m(f"rsix{tag}{nm}Lo", sg(r[f_][1])); m(f"rsix{tag}{nm}Hi", sg(r[f_][2]))
rows6 = []
GROUPS = [("Regime", [("DilCpu", r"M1, $W_{\mathrm{CPU}}$"), ("DilMem", r"M1, $W_{\mathrm{MEM}}$")]),
          ("Kernel code", [("KerPrev", "M1, previous kernel"), ("KerCur", "M1, current kernel")]),
          ("Call-site topology", [("TopoShared", "M2, shared site"), ("TopoDed", "M2, one site per layer")]),
          ("Baseline weight", [("WtEight", r"M1, $w = 8$, \texttt{FaBuMe}"), ("WtEightCtl", r"M1, $w = 8$, \texttt{StDeAd}")]),
          ("Duplicated layers", [("DupBux", r"M1, \texttt{Bu}$\times 3$"), ("DupBuMe", r"M1, \texttt{BuMe}")]),
          ("JIT configuration", [("JitMeasured", "M1, TC = 0 (measured)"), ("JitDefault", "M1, default .NET 8 configuration")])]
for gi_, (g, items) in enumerate(GROUPS):
    if gi_: rows6.append("\\midrule")
    for j, (tag, lab) in enumerate(items):
        r = CS[tag]
        ci = lambda f_: f"${sg(r[f_][0])}$ {{\\scriptsize$[{sg(r[f_][1])}, {sg(r[f_][2])}]$}}"
        rows6.append(f"{g if j == 0 else ''} & {lab} & ${sg(r['delta'])}$ & {r['E0']:.1f} & {r['dI'][0]:.1f} & {ci('tot')} & ${sg(r['w_base'][0])}$ & ${sg(r['w_conf'][0])}$ & ${sg(r['w_shap'][0])}$ & {ci('time')} & {ci('power')}\\\\")
w("tab_decomposition.tex", r"""\begin{table*}[t]
\caption{Decomposition of the interaction in absolute energy (nJ per kernel iteration; 95\% bootstrap intervals in brackets). $\Delta E_{\text{int}} = \delta \cdot E_0$ is split exactly into \emph{work}, the instruction surplus $\Delta I_{\text{int}}$ valued at an energy per instruction, and two \emph{context} terms, the change in time per instruction and the change in power of the configurations involved (two-factor logarithmic mean Divisia split). The split between work and context depends on the energy per instruction used to value the surplus: \emph{base} uses the baseline's (main convention, under which the three terms add up to $\Delta E_{\text{int}}$), \emph{conf.} the configurations' own, \emph{Shapley} their midpoint. \texttt{FaBuMe} unless stated otherwise; sources: Table~\ref{tab:results_delta} (regime), Table~\ref{tab:kernel} (kernel code), Table~\ref{tab:topology} (topology), the weight-sweep counter runs (baseline weight), Table~\ref{tab:dispatch} (duplicated layers) and Section~\ref{subsec:res_jit} (JIT configuration). Instruction counts come from counter runs of the same binaries; they reproduce to within $0.1$ instruction per iteration across protocols.}
\label{tab:decomposition}
\centering\small
\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{%
\begin{tabular}{llrrrrrrrrr}
\toprule
& & $\delta$ & $E_0$ & $\Delta I_{\text{int}}$ & $\Delta E_{\text{int}}$ & \multicolumn{3}{c}{\textbf{Work} (nJ)} & \textbf{Time per} & \textbf{Power}\\
\cmidrule(lr){7-9}
\textbf{Situation} & \textbf{Configuration} & (points) & (nJ) & (instr.) & (nJ) & base & conf. & Shapley & \textbf{instr.} (nJ) & (nJ)\\
\midrule
""" + "\n".join(rows6) + r"""
\bottomrule
\end{tabular}}
\end{table*}
""")

# ---------------------------------------------------------------- revision 7 values
R7 = json.load(open(os.path.join(OUT, "values_rev7.json")))
m("instrPerCallLo", us(R7["instr_per_call"][0])); m("instrPerCallHi", us(R7["instr_per_call"][1]))
m("idleMtwo", us(R7["idle_m2"], 2))
for reg in ("CPU", "MEM"):
    a = R7["acc_m2"][reg]; tag = reg.capitalize()
    m(f"idleShareMtwo{tag}", us(100 * a["share"], 0)); m(f"idleSupMtwo{tag}", str(a["idle"][0])); m(f"idleSubMtwo{tag}", str(a["idle"][1]))
    m(f"idleLostMtwo{tag}", str(len(a["lost"])))
m("ctlPgoInstr", sg(R7["ctl_pgo"]))
m("wtAdjEight", sg(float(MAC["caseWtEightd"]) - float(MAC["caseWtEightCtld"]), 0))
for mach in ("M1", "M2"):
    c, me, r = R7["ab_abs"][mach]; m(f"abAbsCpu{MN[mach]}", sg(c)); m(f"abAbsMem{MN[mach]}", sg(me)); m(f"abAbsRatio{MN[mach]}", us(r, 2))

# ---------------------------------------------------------------- figures
COL = {"M1CPU": "#b2182b", "M2CPU": "#ef8a62", "M1MEM": "#2166ac", "M2MEM": "#67a9cf"}
names = ["FaBuMe", "BuObMe", "BuMe", "BuOb", "FaBu", "ObMe", "StDeAd"]; x = np.arange(len(names)); wd = 0.38
fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
for ax, pair, title in ((axes[0], ("M1CPU", "M2CPU"), r"Compute-bound ($W_{\mathrm{CPU}}$)"), (axes[1], ("M1MEM", "M2MEM"), r"Memory-access ($W_{\mathrm{MEM}}$)")):
    for k, off, lab in ((pair[0], -wd / 2, "Machine 1 (i7-5600U)"), (pair[1], wd / 2, "Machine 2 (i5-1145G7)")):
        v = [SIG[k][c] for c in names]
        ax.bar(x + off, [s["d"] for s in v], wd, yerr=[s["two"] for s in v], color=COL[k], capsize=2, error_kw=dict(lw=0.8), label=lab)
        for xi, s in zip(x + off, v):
            mk = {"*": "*", "dag": "†", "": ""}[s["star"]]
            if mk:
                y = s["d"] + (s["two"] + 1.5) * (1 if s["d"] >= 0 else -1) - (2.5 if s["d"] < 0 else 0)
                ax.text(xi, y, mk, ha="center", fontsize=8)
    ax.axvspan(len(names) - 1.5, len(names) - 0.5, color="grey", alpha=0.12, lw=0)
    ax.axhline(0, color="black", lw=0.7); ax.set_xticks(x)
    ax.set_xticklabels([n if n != "StDeAd" else "StDeAd\n(control)" for n in names], fontsize=8)
    ax.set_title(title, fontsize=10); ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8)
axes[0].set_ylabel(r"Interaction $\delta$ (points of baseline energy)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_regime_v4.pdf")); fig.savefig(os.path.join(OUT, "fig_regime_v4.png"), dpi=150); plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
for ax, pair, title in ((axes[0], ("M1CPU", "M2CPU"), r"Compute-bound ($W_{\mathrm{CPU}}$)"), (axes[1], ("M1MEM", "M2MEM"), r"Memory-access ($W_{\mathrm{MEM}}$)")):
    for k, off, mk, lab in ((pair[0], -0.09, "o", "Machine 1 (i7-5600U)"), (pair[1], 0.09, "s", "Machine 2 (i5-1145G7)")):
        dd = V["dose"][k]
        pts = list(dd["comps"].values())
        ax.scatter([g + off for g, _ in pts], [d for _, d in pts], s=10, color=COL[k], alpha=0.35, lw=0)
        g = [i + off for i in range(4)]; med = [dd["point"][str(i)] for i in range(4)]
        lo = [dd["ci"][str(i)][0] for i in range(4)]; hi = [dd["ci"][str(i)][1] for i in range(4)]
        ax.errorbar(g, med, yerr=[[a - b for a, b in zip(med, lo)], [b - a for a, b in zip(med, hi)]], color=COL[k], marker=mk, ms=5, lw=1.4, capsize=3, label=lab)
    ax.axhline(0, color="grey", lw=0.8, ls="--")
    ns = V["dose"]["M1CPU"]["n"]
    ax.set_xticks([0, 1, 2, 3]); ax.set_xticklabels([f"{i}\n(n = {ns[str(i)]})" for i in range(4)])
    ax.set_xlabel("Number of heap-allocating patterns in the composition"); ax.set_title(title, fontsize=10)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8, loc="upper left")
axes[0].set_ylabel(r"Interaction $\delta$ (points of baseline energy)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_dose_response_v4.pdf")); fig.savefig(os.path.join(OUT, "fig_dose_response_v4.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- numbers.tex
with open(os.path.join(OUT, "numbers.tex"), "w") as fh:
    fh.write("% Generated by make_rev5_tex.py from analyse_rev5_main.py -- do not edit by hand.\n")
    for k in sorted(MAC): fh.write(f"\\newcommand{{\\{k}}}{{{MAC[k]}}}\n")
json.dump({k: {c: {kk: (vv if not isinstance(vv, tuple) else list(vv[:3])) for kk, vv in d.items()} for c, d in L.items()} for k, L in TOPO.items()},
          open(os.path.join(OUT, "topology.json"), "w"), indent=1, default=float)
print(len(MAC), "macros;", "tables:", [f for f in os.listdir(OUT) if f.startswith("tab_")])
