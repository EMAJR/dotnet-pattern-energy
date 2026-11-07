#!/bin/bash
# =====================================================================================
# AMPLIFICATION TEST -- MEMORY regime only.
# Goal: decide whether the small MEM super-additivity (FaBuMe ~+10%, BuObMe ~+9%...)
#       is a REAL residual or measurement noise, by running the SAME configs at two
#       load levels: normal (N=200000) and x5 (N=1000000).
#   - A real interaction PERSISTS or GROWS with load.
#   - An artifact COLLAPSES toward 0 at x5.
#
# Prerequisites: same as run_replication.sh (Linux bare-metal, Intel RAPL, .NET 8 SDK).
# Usage:  bash run_amplification_mem.sh          (REPS defaults to 8)
#         bash run_amplification_mem.sh 12        (to change REPS)
# Output: amp_mem_1x.csv, amp_mem_5x.csv  (+ printed verdict). ~2h unattended.
# =====================================================================================
set -e
REPS=${1:-8}
N1=200000        # normal load
N5=1000000       # x5 load
K=1000
LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0

# Reduced config set: the 7 singles (needed for the additive prediction),
# the super-additive MEM compositions of interest, and the negative control.
CFGS="St De Ad Fa Bu Ob Me FaBuMe BuObMe FaBu BuMe BuOb ObMe StDeAd"

echo "=== 1. RAPL check ==="
[ -d /sys/class/powercap/intel-rapl ] || { echo "!! No intel-rapl -> STOP"; exit 1; }
sudo chmod -R a+r /sys/class/powercap/intel-rapl
E=$(cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null || echo "")
[ -z "$E" ] && { echo "!! energy_uj unreadable -> STOP"; exit 1; }
echo "RAPL OK"

echo "=== 2. Lock environment ==="
sudo cpupower frequency-set -g performance 2>/dev/null || echo "(cpupower n/a)"
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo "(no_turbo n/a)"
export DOTNET_TieredCompilation=0
echo "pinned core = $LC"

echo "=== 3. Build ==="
dotnet build -c Release >/dev/null
BIN=./bin/Release/net8.0/proto

campaign(){  # $1=N  $2=outfile
  echo "rep,config,e_base,e_cfg" > "$2"
  for r in $(seq 1 $REPS); do
    for c in $(printf "%s\n" $CFGS | shuf); do
      EB=$(taskset -c $LC $BIN runk base mem $1 $K 0 | sed -n 's/.*energy_J=\([0-9.]*\).*/\1/p')
      EC=$(taskset -c $LC $BIN runk $c   mem $1 $K 0 | sed -n 's/.*energy_J=\([0-9.]*\).*/\1/p')
      echo "$r,$c,$EB,$EC" >> "$2"
    done
    echo "  [N=$1] pass $r/$REPS ($(date +%H:%M:%S))"
  done
}

echo "=== 4. MEM campaign, normal load (N=$N1) ==="; campaign $N1 amp_mem_1x.csv
echo "=== 5. MEM campaign, x5 load (N=$N5) ==="; campaign $N5 amp_mem_5x.csv

echo "=== 6. AMPLIFICATION VERDICT ==="
python3 - <<'PYEOF'
import csv, statistics, math
C=["St","De","Ad","Fa","Bu","Ob","Me"]; P=lambda n:[c for c in C if c in n]
def deltas(f):
    d={}
    for r in csv.DictReader(open(f)):
        try: eb=float(r["e_base"]); ec=float(r["e_cfg"])
        except: continue
        if eb>0: d.setdefault(r["config"],[]).append(ec/eb)
    rho={k:statistics.median(v) for k,v in d.items()}
    sg={k:rho[k]-1 for k in C if k in rho}; out={}
    for k in rho:
        p=P(k)
        if len(p)<2 or not all(x in sg for x in p): continue
        out[k]=(rho[k]-1-sum(sg[x] for x in p))*100
    return out
d1=deltas("amp_mem_1x.csv"); d5=deltas("amp_mem_5x.csv")
print("  combo      delta @N   delta @5N   -> reading")
for k in ["FaBuMe","BuObMe","FaBu","BuMe","BuOb","ObMe","StDeAd"]:
    a=d1.get(k); b=d5.get(k)
    if a is None or b is None: continue
    if abs(b) < 0.5*abs(a) and abs(b) < 4: tag="COLLAPSES -> noise (additive)"
    elif abs(b) >= abs(a)*0.8:            tag="PERSISTS  -> real residual"
    else:                                 tag="attenuates (borderline)"
    print("  %-8s  %+6.1f%%   %+6.1f%%   %s"%(k,a,b,tag))
print("\nRule: a real memory interaction keeps its magnitude at x5; an idle/scale artifact shrinks toward 0.")
print("Control StDeAd should stay near 0 at both loads.")
PYEOF
echo "=== DONE. Send back: amp_mem_1x.csv, amp_mem_5x.csv ==="
