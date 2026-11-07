# Recomputes only R6-2 (pooling on the identical binary) of analyse_rev6.py, with the modified
# Knapp-Hartung interval, and patches rev5/values_rev6.json. Usage: python3 analyse_rev6_pool.py
import csv, os, json, math
import numpy as np
HERE=os.getcwd(); D=os.path.join(HERE,"data_campaigns"); OUT=os.path.join(HERE,"rev5"); B=4000
rng=np.random.default_rng(23); md=[]; V=json.load(open(os.path.join(OUT,"values_rev6.json")))
def dec(c): return [c[i:i+2] for i in range(0,len(c),2)]
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

json.dump(V, open(os.path.join(OUT, "values_rev6.json"), "w"), indent=1, default=float)
print("\n".join(md))
