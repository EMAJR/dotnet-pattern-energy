#!/bin/bash
# =====================================================================================
# AMPLIFICATION TEST -- COMPUTE regime.
#
# WHY: the amplification test currently covers only the memory regime on Machine 1, so
# RQ3 is only half answered. The paper bounds that honestly, but the gap is cheap to
# close: a real structural interaction keeps its magnitude when the load grows, an
# artifact of scale shrinks toward zero.
#
# Same protocol as run_amplification_mem.sh, compute regime, and energy AND time are
# both captured so the two can be read together.
#
# Usage:  bash run_amplification_cpu.sh [REPS]      (default 8)
# Output: amp_cpu_1x.csv, amp_cpu_5x.csv  (+ printed verdict).  ~30 min.
# =====================================================================================
set -e
REPS=${1:-8}
N1=200000        # nominal load
N5=1000000       # 5x load
K=1000
LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0

# the 7 isolated patterns (needed for the additive prediction), the compositions that
# carry the compute-bound result, and the negative control
CFGS="St De Ad Fa Bu Ob Me FaBuMe BuObMe FaBu BuMe BuOb ObMe StDeAd"

echo "=== 1. RAPL check ==="
[ -d /sys/class/powercap/intel-rapl ] || { echo "!! No intel-rapl -> STOP"; exit 1; }
sudo chmod -R a+r /sys/class/powercap/intel-rapl
cat /sys/class/powercap/intel-rapl:0/energy_uj >/dev/null || { echo "!! energy_uj unreadable -> STOP"; exit 1; }
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
echo "gouverneur verrouille | coeur epingle = $LC | REPS=$REPS"

echo "=== 3. Build + equiv ==="
dotnet build -c Release >/dev/null
BIN=./bin/Release/net8.0/proto
$BIN equiv

ext(){ printf '%s\n' "$2" | sed -n "s/.*$1=\([0-9.]*\).*/\1/p"; }

campaign(){  # $1=N  $2=outfile
  echo "rep,config,e_base,e_cfg,t_base,t_cfg" > "$2"
  for r in $(seq 1 $REPS); do
    for c in $(printf "%s\n" $CFGS | shuf); do
      OB=$(taskset -c $LC $BIN runk base cpu "$1" $K 0)
      OC=$(taskset -c $LC $BIN runk "$c" cpu "$1" $K 0)
      echo "$r,$c,$(ext energy_J "$OB"),$(ext energy_J "$OC"),$(ext time_s "$OB"),$(ext time_s "$OC")" >> "$2"
    done
    echo "  [N=$1] passe $r/$REPS ($(date +%H:%M:%S))"
  done
}

echo "=== 4. Campagne CPU, charge nominale (N=$N1, ~5 min) ==="; campaign $N1 amp_cpu_1x.csv
echo "=== 5. Campagne CPU, charge x5 (N=$N5, ~25 min) ==="  ; campaign $N5 amp_cpu_5x.csv

echo "=== 6. VERDICT D'AMPLIFICATION ==="
python3 - <<'PYEOF'
import csv, statistics as st
PAT=["St","De","Ad","Fa","Bu","Ob","Me"]
def dec(s): return [s[i:i+2] for i in range(0,len(s),2)]
def deltas(f,num,den):
    d={}
    for r in csv.DictReader(open(f)):
        try: a=float(r[num]); b=float(r[den])
        except: continue
        if b>0: d.setdefault(r["config"],[]).append(a/b)
    rho={k:st.median(v) for k,v in d.items()}; out={}
    for k in rho:
        p=dec(k)
        if len(p)<2 or not all(x in rho for x in p): continue
        out[k]=(rho[k]-(1+sum(rho[x]-1 for x in p)))*100
    return out
for lbl,num,den in (("ENERGIE","e_cfg","e_base"),("TEMPS","t_cfg","t_base")):
    d1=deltas("amp_cpu_1x.csv",num,den); d5=deltas("amp_cpu_5x.csv",num,den)
    print("\n--- %s ---"%lbl)
    print("  %-9s %10s %10s   %s"%("combo","delta @N","delta @5N","lecture"))
    for k in ["FaBuMe","BuObMe","FaBu","BuMe","BuOb","ObMe","StDeAd"]:
        a,b=d1.get(k),d5.get(k)
        if a is None or b is None: continue
        if abs(b) < 0.5*abs(a) and abs(b) < 4:  tag="S'EFFONDRE -> artefact d'echelle"
        elif abs(b) >= 0.8*abs(a):              tag="PERSISTE   -> interaction reelle"
        else:                                   tag="s'attenue (limite)"
        print("  %-9s %+9.1f%% %+9.1f%%   %s"%(k,a,b,tag))
print("\nAttendu : les compositions allouantes persistent, le temoin StDeAd reste proche de 0")
print("aux deux charges. Si le temoin derive, le point est a ecarter.")
PYEOF
echo "=== FINI. Renvoie amp_cpu_1x.csv et amp_cpu_5x.csv ==="
