#!/bin/bash
# =====================================================================================
# B1 -- HARDWARE COUNTERS AT SEVERAL BASELINE WEIGHTS  (~1 h with REPS=5)
#
# WHY. The weight sweep contradicts point (4) of section 4.5: if the interaction were a fixed
# cost per iteration, delta(FaBuMe) should fall from +72.5 % at w=1 to about +3.8 % at w=32
# (signatures shrink 18.8x). It falls only to +25.4 %, and delta_energy == delta_time at w=32,
# so the absolute TIME surplus grows about 10x with w. The curve is also non-monotone
# (+5.1 % at w=8, +33.5 % at w=16).
#
# PRE-REGISTERED HYPOTHESES (written before measuring -- do not edit after the run):
#   H1  instruction surplus per iteration CONSTANT across w, time surplus GROWS
#         -> the extra cost is a timing effect (stalls / indirect-branch mispredictions),
#            not extra work; the two-term model describes work only.
#   H2  instruction surplus per iteration GROWS with w
#         -> something structural in the executed code changes with the kernel weight.
#   H3  surplus (instructions or time) NON-MONOTONE in w
#         -> layout / alignment measurement bias suspected -> run B5 before any claim
#            about intermediate weights, and treat the w=32 anchor as unconfirmed.
#
# Per-task divisor is K + 100: runk always executes 100 warm-up tasks, which perf counts.
#
# Usage:  bash run_B1_perf_weights.sh [REPS]     (default 5)
# Output: B1_perf_weights.csv  (+ printed summary)
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
REPS=${1:-5}
WEIGHTS="1 4 8 16 32"
CFGS="St De Ad Fa Bu Ob Me FaBuMe BuObMe BuMe ObMe StDeAd"
OUT=B1_perf_weights.csv
TMP=$(mktemp -d)

check_rapl; check_perf; lock_env
export DOTNET_TieredCompilation=0
dotnet build -c Release >/dev/null || { echo "!! build failed -> STOP"; exit 1; }
for w in $WEIGHTS; do $BIN equiv $w | tail -1; $BIN equiv $w >/dev/null || { echo "!! equiv failed at w=$w -> STOP"; exit 1; }; done

kfor(){ local k=$(( 5000 / $1 )); [ "$k" -lt 150 ] && k=150; echo $k; }

echo "weight,rep,config,K,warmup,cycles,instructions,branches,branch_misses,l1d_misses,dtlb_misses,time_s,energy_J" > "$OUT"
for r in $(seq 1 $REPS); do
  for w in $(printf "%s\n" $WEIGHTS | shuf); do
    K=$(kfor $w)
    for c in base $(printf "%s\n" $CFGS | shuf); do
      perf_run "$TMP/p" "$TMP/o" taskset -c $LC $BIN runk "$c" cpu $N $K 0 $w
      O=" $(cat "$TMP/o")"
      echo "$w,$r,$c,$K,100,$(pget $TMP/p cycles),$(pget $TMP/p instructions),$(pget $TMP/p branches),$(pget $TMP/p branch-misses),$(pget $TMP/p L1-dcache-load-misses),$(pget $TMP/p dTLB-load-misses),$(ext time_s "$O"),$(ext energy_J "$O")" >> "$OUT"
    done
    echo "  pass $r/$REPS  w=$w  ($(date +%H:%M:%S))"
  done
done
rm -rf "$TMP"

echo "=== SUMMARY (I will redo the full analysis on the CSV) ==="
python3 - "$OUT" <<'PYEOF'
import csv, sys, statistics as st
N = 200000
rows = list(csv.DictReader(open(sys.argv[1])))
def dec(s): return [s[i:i+2] for i in range(0, len(s), 2)]
def num(x):
    try: return float(x)
    except: return None
W = sorted({int(r["weight"]) for r in rows})
COMP = ["FaBuMe", "BuObMe", "BuMe", "ObMe", "StDeAd"]
print("%-7s %4s %14s %14s %10s %10s" % ("comp", "w", "instr/iter", "brmiss/iter", "d_time %", "d_energy %"))
for c in COMP:
    for w in W:
        R = [r for r in rows if int(r["weight"]) == w]
        tasks = {r["config"]: (int(r["K"]) + int(r["warmup"])) for r in R}
        def med(cfg, col):
            v = [num(r[col]) for r in R if r["config"] == cfg and num(r[col]) is not None]
            return st.median(v) if v else None
        def surplus(col):
            b = med("base", col); x = med(c, col); ps = [med(p, col) for p in dec(c)]
            if None in [b, x] + ps: return float("nan")
            return ((x - b) - sum(p - b for p in ps)) / (tasks[c] * N)
        def delta(col):
            ratios = {}
            for rep in {r["rep"] for r in R}:
                base = [num(r[col]) for r in R if r["rep"] == rep and r["config"] == "base"]
                if not base or not base[0]: continue
                for r in R:
                    if r["rep"] == rep and num(r[col]) is not None:
                        ratios.setdefault(r["config"], []).append(num(r[col]) / base[0])
            rho = {k: st.median(v) for k, v in ratios.items()}
            if c not in rho or not all(p in rho for p in dec(c)): return float("nan")
            return 100 * (rho[c] - (1 + sum(rho[p] - 1 for p in dec(c))))
        print("%-7s %4d %14.2f %14.3f %+10.1f %+10.1f" % (c, w, surplus("instructions"), surplus("branch_misses"), delta("time_s"), delta("energy_J")))
    print()
print("Reading: compare instr/iter across w for each composition.")
print("  ~constant + d_time falling slower than the signatures -> H1 ; growing -> H2 ; zig-zag -> H3 (run B5).")
PYEOF
echo "=== DONE. Send me $OUT ==="
