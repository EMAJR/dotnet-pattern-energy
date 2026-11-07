#!/bin/bash
# =====================================================================================
# B4 -- INVOCATION TOPOLOGY 2x2 (+1)  (~1 h)
#
# The reviewer's main methodological objection: pattern category and invocation topology are
# confounded. Indirection patterns are nested wrappers (monomorphic sites); allocating patterns
# all go through ONE shared site sides[s].Step. This experiment keeps the allocating patterns
# and changes ONLY how they are invoked:
#     topo 0  shared interface call site           (current bench)
#     topo 1  one interface call site per layer    (monomorphic sites, still interface dispatch)
#     topo 2  one direct call per layer on a sealed typed field (no interface dispatch)
# Every configuration is compared against the baseline of the SAME topology, so additive
# predictions are computed within a topology. Checksums are verified for all combinations.
# topo 2 is, literally, the eco-design guideline of section 5.1 applied inside the bench.
#
# PRE-REGISTERED OUTCOMES (both are results):
#   T1  topo 1 and topo 2: instruction surplus of compositions drops to the mono level
#       (about 3 per iteration or less) AND delta_energy drops sharply
#         -> the shared polymorphic site is the cause of the energy interaction; the guideline
#            is validated in the bench.
#   T2  instruction surplus drops but delta_energy stays high
#         -> the shared site explains the extra WORK but not the extra ENERGY; the energy
#            interaction has another, still unidentified cause, and the article must say so.
#   T3  instruction surplus does not drop
#         -> the dispatch-site explanation is wrong; section 4.5 must be withdrawn.
#
# Usage:  bash run_B4_topology.sh [REPS_ENERGY] [REPS_PERF] [cpu|mem]   (defaults 8, 3, cpu)
# Output: B4_energy.csv, B4_perf.csv (cpu)  or  B4_energy_mem.csv, B4_perf_mem.csv (mem)
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
RE=${1:-8}; RP=${2:-3}; REGIME=${3:-cpu}
SUF=""; [ "$REGIME" != cpu ] && SUF="_$REGIME"
FE="B4_energy${SUF}.csv"; FP="B4_perf${SUF}.csv"
echo "regime=$REGIME -> $FE, $FP"
KE=1000; KP=2000
CFGS="St De Ad Fa Bu Ob Me FaBu BuMe BuOb ObMe FaBuMe BuObMe StDeAd"
TOPOS="0 1 2"

check_rapl; check_perf; lock_env
export DOTNET_TieredCompilation=0
build_patched
TMP=$(mktemp -d)

echo "=== 1. energy + time, paired per (config, topology) (~35 min) ==="
echo "rep,topo,config,e_base,e_cfg,t_base,t_cfg,alloc_cfg" > "$FE"
for r in $(seq 1 $RE); do
  for item in $( (for t in $TOPOS; do for c in $CFGS; do echo "$t:$c"; done; done) | shuf); do
    t=${item%%:*}; c=${item#*:}
    OB=" $(taskset -c $LC $BIN runktopo base $REGIME $N $KE 0 $t 1 1)"
    OC=" $(taskset -c $LC $BIN runktopo $c $REGIME $N $KE 0 $t 1 1)"
    echo "$r,$t,$c,$(ext energy_J "$OB"),$(ext energy_J "$OC"),$(ext time_s "$OB"),$(ext time_s "$OC"),$(ext alloc_per_iter "$OC")" >> "$FE"
  done
  echo "  [energy] pass $r/$RE ($(date +%H:%M:%S))"
done

echo "=== 2. hardware counters (~20 min) ==="
echo "rep,topo,config,K,warmup,cycles,instructions,branches,branch_misses,time_s" > "$FP"
for r in $(seq 1 $RP); do
  for t in $(printf "%s\n" $TOPOS | shuf); do
    for c in base $(printf "%s\n" $CFGS | shuf); do
      perf_run "$TMP/p" "$TMP/o" taskset -c $LC $BIN runktopo $c $REGIME $N $KP 0 $t 1 1
      O=" $(cat $TMP/o)"
      echo "$r,$t,$c,$KP,100,$(pget $TMP/p cycles),$(pget $TMP/p instructions),$(pget $TMP/p branches),$(pget $TMP/p branch-misses),$(ext time_s "$O")" >> "$FP"
    done
  done
  echo "  [perf] pass $r/$RP ($(date +%H:%M:%S))"
done
rm -rf "$TMP"

echo "=== SUMMARY ==="
python3 - "$FE" "$FP" <<'PYEOF'
import csv, statistics as st
N = 200000
def dec(s): return [s[i:i+2] for i in range(0, len(s), 2)]
COMP = ["FaBu", "BuMe", "BuOb", "ObMe", "FaBuMe", "BuObMe", "StDeAd"]
import sys
E = list(csv.DictReader(open(sys.argv[1])))
P = list(csv.DictReader(open(sys.argv[2])))
print("%-7s | %s" % ("comp", "   ".join("topo%d: dE / dT / instr" % t for t in (0, 1, 2))))
for c in COMP:
    line = "%-7s |" % c
    for t in ("0", "1", "2"):
        vals = []
        for a, b in (("e_cfg", "e_base"), ("t_cfg", "t_base")):
            d = {}
            for r in E:
                if r["topo"] != t: continue
                try: d.setdefault(r["config"], []).append(float(r[a]) / float(r[b]))
                except: pass
            rho = {k: st.median(v) for k, v in d.items()}
            vals.append(100 * (rho[c] - (1 + sum(rho[p] - 1 for p in dec(c)))) if c in rho and all(p in rho for p in dec(c)) else float("nan"))
        D = {}
        for r in P:
            if r["topo"] != t: continue
            try: D.setdefault(r["config"], []).append(float(r["instructions"]))
            except: pass
        M = {k: st.median(v) for k, v in D.items()}
        ins = (((M[c] - M["base"]) - sum(M[p] - M["base"] for p in dec(c))) / ((int(P[0]["K"]) + 100) * N)
               if "base" in M and c in M and all(p in M for p in dec(c)) else float("nan"))
        line += "   %+6.1f / %+6.1f / %5.1f" % (vals[0], vals[1], ins)
    print(line)
print("\nT1: topo 1-2 instr ~<=3 and dE collapses | T2: instr drops, dE stays | T3: instr does not drop")
PYEOF
echo "=== DONE. Send me $FE and $FP ==="
