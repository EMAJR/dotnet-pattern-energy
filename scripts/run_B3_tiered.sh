#!/bin/bash
# =====================================================================================
# B3 -- DOES THE EFFECT SURVIVE THE .NET 8 DEFAULT JIT POLICY?  (~1 h)
#
# All campaigns of record run with TieredCompilation=0 (no dynamic PGO). Production .NET 8
# runs with tiering + dynamic PGO, which enables guarded devirtualization. If PGO guards the
# shared call site, the polymorphic surplus may shrink, vanish or change shape -- and the
# scope of the article changes with it. This must be known before submitting.
#
# DESIGN: the dispatch experiment (same 16 configurations as run_dispatch.sh v2), measured
# with TWO binaries built from the SAME source, interleaved inside every pass:
#     default : TieredCompilation=0                 (campaign configuration)
#     tiered  : TieredCompilation=1 + TieredPGO=1    (.NET 8 default)
# Both use the same longer warm-up (300 tasks, 1.5 s settle, 100 more tasks) so that the
# tiered JIT reaches Tier-1 before measuring. jit_during (methods compiled inside the measured
# window) is recorded: any run with jit_during > 0 is NOT steady state and is reported.
#
# PRE-REGISTERED OUTCOMES (both are results):
#   P1  tiered reproduces the default pattern (mono ~3/iter, poly ~25-40/iter)
#         -> the effect holds in production configuration; claims unchanged in scope.
#   P2  tiered shrinks the POLYMORPHIC surplus markedly while mono stays small
#         -> PGO-driven devirtualization partly rescues the shared site; the article must
#            state the effect for the non-PGO configuration and quantify the PGO case.
#   P3  tiered changes the picture qualitatively (e.g. surplus in mono configs too)
#         -> mechanism claims are configuration-specific; rewrite section 4.5 accordingly.
#
# Usage:  bash run_B3_tiered.sh [REPS_ENERGY] [REPS_PERF]     (defaults 6 and 3)
# Output: B3_energy.csv, B3_perf.csv  (+ printed summary)
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
RE=${1:-6}; RP=${2:-3}
KE=1000; KP=3000
SPEC="St:1 De:1 Ad:1 Fa:1 Bu:1 Me:1 Ob:1 Bu:2 Me:2 Ob:2 Bu:3 Me:3 BuMe:1 ObMe:1 FaBuMe:1 StDeAd:1"
export BENCH_WARMUP=300 BENCH_SETTLE_MS=1500
WARM_TOTAL=400   # 300 + 100 after settle (perf counts them)

check_rapl; check_perf; lock_env
build_patched
build_tiered
TMP=$(mktemp -d)

runbin(){ # $1=default|tiered, rest = runktopo args
  local which=$1; shift
  if [ "$which" = default ]; then run_default taskset -c $LC $BIN runktopo "$@"
  else run_tiered taskset -c $LC $BIN_T runktopo "$@"; fi
}

echo "=== 1. energy + time, paired, interleaved binaries (~35 min) ==="
echo "rep,binary,config,dup,e_base,e_cfg,t_base,t_cfg,jit_base,jit_cfg" > B3_energy.csv
for r in $(seq 1 $RE); do
  for item in $( (for sp in $SPEC; do echo "default:$sp"; echo "tiered:$sp"; done) | shuf); do
    b=${item%%:*}; sp=${item#*:}; c=${sp%%:*}; d=${sp##*:}
    OB=" $(runbin $b base cpu $N $KE 0 0 1 1)"
    OC=" $(runbin $b $c cpu $N $KE 0 0 $d 1)"
    echo "$r,$b,$c,$d,$(ext energy_J "$OB"),$(ext energy_J "$OC"),$(ext time_s "$OB"),$(ext time_s "$OC"),$(ext jit_during "$OB"),$(ext jit_during "$OC")" >> B3_energy.csv
  done
  echo "  [energy] pass $r/$RE ($(date +%H:%M:%S))"
done

echo "=== 2. hardware counters, both binaries (~20 min) ==="
echo "rep,binary,config,dup,K,warmup,cycles,instructions,branches,branch_misses,time_s,jit_during" > B3_perf.csv
for r in $(seq 1 $RP); do
  for b in $(printf "default\ntiered\n" | shuf); do
    for sp in base:1 $(printf "%s\n" $SPEC | shuf); do
      c=${sp%%:*}; d=${sp##*:}
      if [ "$b" = default ]; then perf_run "$TMP/p" "$TMP/o" env DOTNET_TieredCompilation=0 taskset -c $LC $BIN runktopo $c cpu $N $KP 0 0 $d 1
      else perf_run "$TMP/p" "$TMP/o" env -u DOTNET_TieredCompilation DOTNET_TieredPGO=1 taskset -c $LC $BIN_T runktopo $c cpu $N $KP 0 0 $d 1; fi
      O=" $(cat $TMP/o)"
      echo "$r,$b,$c,$d,$KP,$WARM_TOTAL,$(pget $TMP/p cycles),$(pget $TMP/p instructions),$(pget $TMP/p branches),$(pget $TMP/p branch-misses),$(ext time_s "$O"),$(ext jit_during "$O")" >> B3_perf.csv
    done
  done
  echo "  [perf] pass $r/$RP ($(date +%H:%M:%S))"
done
rm -rf "$TMP"

echo "=== SUMMARY ==="
python3 - <<'PYEOF'
import csv, statistics as st
N = 200000
def key(c, d): return c + ("x%s" % d if d != "1" else "")
TESTS = [("Bux2",["Bu"]*2,"mono"),("Mex2",["Me"]*2,"mono"),("Obx2",["Ob"]*2,"mono"),("Bux3",["Bu"]*3,"mono"),
         ("Mex3",["Me"]*3,"mono"),("BuMe",["Bu","Me"],"POLY"),("ObMe",["Ob","Me"],"POLY"),
         ("FaBuMe",["Fa","Bu","Me"],"POLY"),("StDeAd",["St","De","Ad"],"chain")]
E = list(csv.DictReader(open("B3_energy.csv")))
bad = sum(1 for r in E if (r["jit_cfg"] not in ("0", "")) or (r["jit_base"] not in ("0", "")))
print("energy runs with JIT activity inside the window: %d / %d" % (bad, len(E)))
for b in ("default", "tiered"):
    print("\n--- %s ---" % b)
    for lbl, a, bb in (("energy", "e_cfg", "e_base"), ("time", "t_cfg", "t_base")):
        d = {}
        for r in E:
            if r["binary"] != b: continue
            try: d.setdefault(key(r["config"], r["dup"]), []).append(float(r[a]) / float(r[bb]))
            except: pass
        rho = {k: st.median(v) for k, v in d.items()}
        line = "  delta %-6s" % lbl
        for k, ps, s in TESTS:
            if k in rho and all(p in rho for p in ps):
                line += "  %s %+.1f" % (k, 100 * (rho[k] - (1 + sum(rho[p] - 1 for p in ps))))
        print(line)
P = list(csv.DictReader(open("B3_perf.csv")))
for b in ("default", "tiered"):
    D = {}
    for r in P:
        if r["binary"] != b: continue
        try: D.setdefault(key(r["config"], r["dup"]), []).append(float(r["instructions"]))
        except: pass
    M = {k: st.median(v) for k, v in D.items()}
    if "base" not in M: continue
    tasks = int(P[0]["K"]) + int(P[0]["warmup"])
    line = "  instr surplus/iter (%s)" % b
    for k, ps, s in TESTS:
        if k in M and all(p in M for p in ps):
            line += "  %s %.1f" % (k, ((M[k] - M["base"]) - sum(M[p] - M["base"] for p in ps)) / (tasks * N))
    print(line)
PYEOF
echo "=== DONE. Send me B3_energy.csv and B3_perf.csv ==="
