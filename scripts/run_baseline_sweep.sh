#!/bin/bash
# =====================================================================================
# BASELINE-WEIGHT SWEEP  (v2)
#
# Question: our ratios rho are divided by a deliberately minimal baseline. Application-level
# studies divide by a much heavier one. What happens to the isolated signatures rho_p AND to
# the interaction delta as the baseline is made progressively heavier?
#
# Method: the kernel repeats its arithmetic step `kernel_rep` times per iteration. The patterns
# are untouched -- their per-iteration work is identical at every weight. Only the denominator
# of every ratio changes.
#
# WHAT CHANGED FROM v1 (and why):
#   v1 scaled K down as 1000/m to keep each measurement window at ~1 s. That was the wrong
#   criterion: the uncertainty on delta compounds four medians, so what matters is the NUMBER
#   of independent samples, not the window duration. At weight 32 we were left with K=31 and
#   10 repetitions, and the pure-indirection control drifted to -22 % -- i.e. the campaign was
#   invalid at the heavy weights.
#   v2 floors K at 120 and raises REPS to 20. The isolated signatures were already clean in v1
#   and are unaffected; this only fixes delta.
#
# Usage:  bash run_baseline_sweep.sh [REPS]      (default 20)
# Output: sweep_cpu.csv  (+ sweep_mem.csv if ALSO_MEM=1)
#         plus a per-weight control check printed at the end.
# =====================================================================================
set -e
REPS=${1:-20}
N=200000
WEIGHTS="1 2 4 8 16 32"
KFLOOR=120
ALSO_MEM=${ALSO_MEM:-0}

# 7 isolated patterns (needed for rho_p and for the additive prediction) + the compositions
# that carry the result + the pure-indirection control.
CFGS="St De Ad Fa Bu Ob Me FaBuMe BuObMe BuMe ObMe StDeAd"

LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0

echo "=== 1. RAPL check ==="
[ -d /sys/class/powercap/intel-rapl ] || { echo "!! RAPL indisponible. STOP."; exit 1; }
sudo chmod -R a+r /sys/class/powercap/intel-rapl
cat /sys/class/powercap/intel-rapl:0/energy_uj >/dev/null || { echo "!! energy_uj illisible. STOP."; exit 1; }
echo "RAPL OK"

echo "=== 2. Lock environment (BLOQUANT) ==="
command -v cpupower >/dev/null 2>&1 || {
  echo "!! cpupower ABSENT -> frequence non verrouillee, campagne invalide."
  echo "   sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"; exit 1; }
sudo cpupower frequency-set -g performance >/dev/null 2>&1
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo >/dev/null 2>&1 || echo "(no_turbo indispo, non bloquant)"
BAD=$(grep -L performance /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | wc -l)
GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
[ "$BAD" -eq 0 ] && [ "$GOV" = "performance" ] || { echo "!! Gouverneur='$GOV'. STOP."; exit 1; }
export DOTNET_TieredCompilation=0
echo "gouverneur verrouille | coeur epingle = $LC | REPS=$REPS | K plancher=$KFLOOR"

echo "=== 3. Build ==="
dotnet build -c Release >/dev/null
BIN=./bin/Release/net8.0/proto

echo "=== 4. Equivalence a chaque poids ==="
for M in $WEIGHTS; do
  echo -n "  poids $M : "
  $BIN equiv "$M" | tail -1
done

ext(){ printf '%s\n' "$2" | sed -n "s/.*$1=\([0-9.]*\).*/\1/p"; }

sweep(){ # $1=regime  $2=outfile
  echo "kernel_rep,K,rep,config,e_base,e_cfg,t_base,t_cfg" > "$2"
  for M in $WEIGHTS; do
    K=$(( 1000 / M )); [ "$K" -lt "$KFLOOR" ] && K=$KFLOOR
    echo "  [$1] poids=$M K=$K REPS=$REPS  ($(date +%H:%M:%S))"
    for r in $(seq 1 $REPS); do
      for c in $(printf "%s\n" $CFGS | shuf); do
        OB=$(taskset -c $LC $BIN runk base $1 $N $K 0 "$M")
        OC=$(taskset -c $LC $BIN runk "$c" $1 $N $K 0 "$M")
        echo "$M,$K,$r,$c,$(ext energy_J "$OB"),$(ext energy_J "$OC"),$(ext time_s "$OB"),$(ext time_s "$OC")" >> "$2"
      done
    done
  done
}

echo "=== 5. Balayage, regime calcul (~2 h 10) ==="
sweep cpu sweep_cpu.csv

if [ "$ALSO_MEM" = "1" ]; then
  echo "=== 6. Balayage, regime memoire ==="
  sweep mem sweep_mem.csv
fi

echo "=== 7. Controle de validite par poids ==="
python3 - <<'PYEOF'
import csv, statistics as st
PAT=["St","De","Ad","Fa","Bu","Ob","Me"]
def dec(s): return [s[i:i+2] for i in range(0,len(s),2)]
rows=list(csv.DictReader(open("sweep_cpu.csv")))
W=sorted({int(r["kernel_rep"]) for r in rows})
print("  poids   max(rho_p-1)   delta(StDeAd)   verdict")
for w in W:
    sub=[r for r in rows if int(r["kernel_rep"])==w]
    rho={}
    for c in {r["config"] for r in sub}:
        v=[float(r["e_cfg"])/float(r["e_base"]) for r in sub if r["config"]==c and float(r["e_base"])>0]
        if v: rho[c]=st.median(v)
    if not all(p in rho for p in PAT) or "StDeAd" not in rho: continue
    sig=(max(rho[p] for p in PAT)-1)*100
    d=(rho["StDeAd"]-(1+sum(rho[p]-1 for p in dec("StDeAd"))))*100
    ok = "OK" if abs(d) < 8 else "!! TEMOIN DERIVE -> point a ecarter"
    print("  %-6d %12.1f%% %14.1f%%   %s"%(w,sig,d,ok))
print("\n  Attendu : max(rho_p-1) decroissant, et |delta(StDeAd)| petit a TOUS les poids.")
print("  Si le temoin derive a un poids, ce point n'est pas exploitable.")
PYEOF

echo "=== FINI. Renvoie sweep_cpu.csv ==="
