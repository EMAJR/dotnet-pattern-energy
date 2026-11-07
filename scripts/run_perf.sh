#!/bin/bash
# =====================================================================================
# HARDWARE PERFORMANCE COUNTERS -- the last step of the mechanism analysis.
#
# WHERE WE STAND
#   Four candidate explanations are already excluded by measurement: allocation volume
#   (exactly additive), generation-0 collection count (additive), the invariance of both
#   across load regimes, and collector pause duration (additive, <3.3 % of runtime).
#   What remains is the ALLOCATION PATH -- the mutator-side cost of obtaining memory.
#
# WHAT THIS MEASURES
#   perf PMU counters per configuration: cycles, instructions (hence IPC), L1 data-cache
#   load misses, dTLB load misses, and page faults.
#
# WHAT IT COULD SHOW -- both outcomes are results, do NOT assume one
#   (a) cache/TLB misses super-additive while instructions stay additive
#       -> two allocation sources degrade locality; the allocation path is confirmed.
#   (b) every counter additive
#       -> the allocation path is excluded too, and the search moves elsewhere.
#   The GC-pause campaign refuted the collector hypothesis; this one may equally refute
#   the allocation-path hypothesis. Run it ready for that.
#
# KNOWN LIMITATION
#   perf counts the WHOLE process: .NET startup, JIT, the 100 warm-up tasks, then the
#   measured loop. K is therefore set high (5000) so the measured loop accounts for
#   roughly 97 % of process activity, and every configuration is compared against the
#   baseline measured the same way, so the constant overhead largely cancels.
#
# Usage:  bash run_perf.sh [REPS]        (default 8)
# Output: perf_cpu.csv  (+ printed additivity verdict)
# =====================================================================================
set -e
REPS=${1:-8}
N=200000
K=5000          # high, so the measured loop dominates the process
LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0

CFGS="St De Ad Fa Bu Ob Me FaBuMe BuObMe BuMe ObMe StDeAd"

echo "=== 1. perf available and permitted? ==="
command -v perf >/dev/null 2>&1 || {
  echo "!! perf ABSENT.  sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"; exit 1; }
PARANOID=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo 3)
if [ "$PARANOID" -gt 1 ]; then
  echo "  perf_event_paranoid = $PARANOID -> lowering to 1 for this session"
  echo 1 | sudo tee /proc/sys/kernel/perf_event_paranoid >/dev/null
fi

echo "=== 2. which counters does this CPU expose? ==="
EVENTS="cycles,instructions"
for e in L1-dcache-load-misses dTLB-load-misses page-faults; do
  if perf stat -e "$e" true >/dev/null 2>&1; then EVENTS="$EVENTS,$e"; echo "  OK   $e"
  else echo "  n/a  $e (skipped)"; fi
done
echo "  -> events: $EVENTS"

echo "=== 3. Lock environment (BLOQUANT) ==="
command -v cpupower >/dev/null 2>&1 || { echo "!! cpupower ABSENT -> STOP"; exit 1; }
sudo cpupower frequency-set -g performance >/dev/null 2>&1
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo >/dev/null 2>&1 || echo "(no_turbo indispo)"
BAD=$(grep -L performance /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | wc -l)
[ "$BAD" -eq 0 ] || { echo "!! gouverneur non verrouille sur tous les coeurs. STOP."; exit 1; }
export DOTNET_TieredCompilation=0
echo "gouverneur verrouille | coeur epingle = $LC | K=$K | REPS=$REPS"

echo "=== 4. Build + equiv ==="
dotnet build -c Release >/dev/null
BIN=./bin/Release/net8.0/proto
$BIN equiv

# run one configuration under perf and emit "event=value" pairs
measure(){  # $1=config
  perf stat -x, -e "$EVENTS" -- taskset -c $LC $BIN runk "$1" cpu $N $K 0 2>&1 \
    | awk -F, 'NF>=3 && $1 ~ /^[0-9]+$/ {printf "%s=%s\n",$3,$1}'
}
get(){ printf '%s\n' "$2" | sed -n "s/^$1=\([0-9]*\)$/\1/p" | head -1; }

echo "=== 5. Campagne (~25 min) ==="
echo "rep,config,cycles,instructions,l1d_misses,dtlb_misses,page_faults" > perf_cpu.csv
for r in $(seq 1 $REPS); do
  for c in base $(printf "%s\n" $CFGS | shuf); do
    O=$(measure "$c")
    echo "$r,$c,$(get cycles "$O"),$(get instructions "$O"),$(get L1-dcache-load-misses "$O"),$(get dTLB-load-misses "$O"),$(get page-faults "$O")" >> perf_cpu.csv
  done
  echo "  passe $r/$REPS ($(date +%H:%M:%S))"
done

echo "=== 6. VERDICT : additivite des compteurs ==="
python3 - <<'PYEOF'
import csv, statistics as st
PAT=["St","De","Ad","Fa","Bu","Ob","Me"]
def dec(s): return [s[i:i+2] for i in range(0,len(s),2)]
rows=list(csv.DictReader(open("perf_cpu.csv")))
cols=["cycles","instructions","l1d_misses","dtlb_misses","page_faults"]
D={c:{} for c in cols}
for r in rows:
    for c in cols:
        try: D[c].setdefault(r["config"],[]).append(float(r[c]))
        except (ValueError, KeyError): pass
M={c:{k:st.median(v) for k,v in D[c].items() if v} for c in cols}
base={c:M[c].get("base",0) for c in cols}

print("  Valeurs nettes (configuration moins baseline), et ecart a l'additivite.")
print("  %-9s %12s %12s %12s %12s"%("config","instructions","l1d_misses","dtlb_misses","IPC"))
for k in ["Fa","Bu","Ob","Me","ObMe","BuMe","FaBuMe","BuObMe","StDeAd"]:
    if k not in M["cycles"]: continue
    ipc = M["instructions"][k]/M["cycles"][k] if M["cycles"].get(k) else float('nan')
    print("  %-9s %12.3e %12.3e %12.3e %12.3f"%(
        k, M["instructions"][k]-base["instructions"],
           M["l1d_misses"].get(k,0)-base["l1d_misses"],
           M["dtlb_misses"].get(k,0)-base["dtlb_misses"], ipc))
print()
print("  %-9s %14s %14s %14s"%("composition","instr. dev.","L1D dev.","dTLB dev."))
for k in ["ObMe","BuMe","FaBuMe","BuObMe","StDeAd"]:
    if k not in M["cycles"]: continue
    ps=dec(k); line="  %-9s"%k
    for c in ("instructions","l1d_misses","dtlb_misses"):
        if not all(p in M[c] for p in ps) or k not in M[c]: line+="%14s"%"--"; continue
        net=M[c][k]-base[c]; pred=sum(M[c][p]-base[c] for p in ps)
        line+="%13.1f%%"%(100*(net-pred)/pred) if abs(pred)>1 else "%14s"%"--"
    print(line)
print("\n  Lecture : si 'instr. dev.' est proche de 0 mais 'L1D dev.' et 'dTLB dev.' sont")
print("  fortement positifs, deux sources d'allocation degradent la localite -> le chemin")
print("  d'allocation est confirme. Si tout est proche de 0, il est ecarte lui aussi.")
print("  Le temoin StDeAd doit rester proche de 0 sur les trois colonnes.")
PYEOF

echo "=== FINI. Renvoie perf_cpu.csv ==="
