#!/bin/bash
# =====================================================================================
# GC PAUSE CAMPAIGN -- the discriminating experiment for the mechanism.
#
# WHAT WE ALREADY KNOW
#   - allocation volume is exactly additive            (0-byte deviation over 26 compositions)
#   - generation-0 collection COUNT is additive        (0.10 % deviation)
#   - the energy penalty is almost entirely a TIME penalty
#       (delta_time tracks delta_energy at r = +0.989 compute-bound, +0.992 memory-bound)
#
# THEREFORE the extra work must be in how much work EACH collection does, not in how often
# the collector runs. That is exactly what GC.GetTotalPauseDuration() measures.
#
# THE TEST
#   additivity of pause time:   pause(AB)  vs  pause(A) + pause(B)
#   cost per collection:        pause_ms / gen0
#   If pause time is super-additive while gen0 is additive -> each collection does more work
#   when two independent allocation sources coexist. Mechanism identified.
#   If pause time is additive too -> the extra time is NOT in the collector, and the last
#   candidate is eliminated.
#
# This campaign does not need RAPL (no energy is used), but the frequency is still locked
# because pause durations depend on clock speed.
#
# Usage:  bash run_gcpause.sh [PASSES]        (default 10)
# Output: gcpause_cpu.csv, gcpause_mem.csv
# =====================================================================================
set -e
PASSES=${1:-10}
N=200000
K=2000          # enough to trigger thousands of gen-0 collections for allocating configs

LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0

echo "=== 1. Lock environment (BLOQUANT) ==="
command -v cpupower >/dev/null 2>&1 || {
  echo "!! cpupower ABSENT -> frequence non verrouillee, les temps de pause seraient invalides."
  echo "   sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"; exit 1; }
sudo cpupower frequency-set -g performance >/dev/null 2>&1
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo >/dev/null 2>&1 || echo "(no_turbo indispo, non bloquant)"
BAD=$(grep -L performance /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | wc -l)
GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
[ "$BAD" -eq 0 ] && [ "$GOV" = "performance" ] || { echo "!! Gouverneur='$GOV'. STOP."; exit 1; }
export DOTNET_TieredCompilation=0
echo "gouverneur verrouille | coeur epingle = $LC | K=$K | passes=$PASSES"

echo "=== 2. Build + equiv ==="
dotnet build -c Release >/dev/null
BIN=./bin/Release/net8.0/proto
$BIN equiv

campaign(){  # $1=regime  $2=outfile
  FIRST=1
  for p in $(seq 1 $PASSES); do
    echo "  [$1] passe $p/$PASSES  ($(date +%H:%M:%S))"
    OUT=$(taskset -c $LC $BIN matrixk "$1" $N $K 0)
    if [ "$FIRST" -eq 1 ]; then
      echo "pass,$(printf '%s\n' "$OUT" | head -1)" > "$2"
      FIRST=0
    fi
    printf '%s\n' "$OUT" | tail -n +2 | sed "s/^/$p,/" >> "$2"
  done
}

echo "=== 3. Campagne CPU (~20 min) ==="
campaign cpu gcpause_cpu.csv
echo "=== 4. Campagne MEMOIRE (~60 min) ==="
campaign mem gcpause_mem.csv

echo "=== 5. Verdict rapide : additivite du temps de pause ==="
python3 - <<'PYEOF'
import csv, statistics as st
PAT=["St","De","Ad","Fa","Bu","Ob","Me"]; ALLOC={"Fa","Bu","Ob","Me"}
def dec(s): return [s[i:i+2] for i in range(0,len(s),2)]
for lbl,f in (("CPU","gcpause_cpu.csv"),("MEM","gcpause_mem.csv")):
    try: rows=list(csv.DictReader(open(f)))
    except FileNotFoundError: continue
    P,G={},{}
    for r in rows:
        P.setdefault(r["config"],[]).append(float(r["gc_pause_ms"]))
        G.setdefault(r["config"],[]).append(int(r["gen0"]))
    pm={k:st.median(v) for k,v in P.items()}
    gm={k:st.median(v) for k,v in G.items()}
    print("\n=== %s ==="%lbl)
    print("%-9s %11s %9s %12s %11s %9s"%("config","pause_ms","gen0","us/collecte","pause pred.","ecart %"))
    for c in ["Fa","Bu","Ob","Me","ObMe","FaBu","BuMe","BuOb","FaBuMe","BuObMe","StDeAd"]:
        if c not in pm: continue
        ps=dec(c); per = 1000*pm[c]/gm[c] if gm[c] else float('nan')
        if len(ps)>1 and all(p in pm for p in ps):
            pred=sum(pm[p] for p in ps)
            dev=100*(pm[c]-pred)/pred if pred else float('nan')
            print("%-9s %11.1f %9d %12.1f %11.1f %+8.1f"%(c,pm[c],gm[c],per,pred,dev))
        else:
            print("%-9s %11.1f %9d %12.1f %11s %9s"%(c,pm[c],gm[c],per,"-","-"))
    print("\n  Lecture : 'ecart %' > 0 et grand => temps de pause SUPER-ADDITIF.")
    print("            'us/collecte' qui augmente avec 2 sources => chaque collecte travaille plus.")
PYEOF

echo "=== FINI. Renvoie gcpause_cpu.csv et gcpause_mem.csv ==="
