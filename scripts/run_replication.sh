#!/bin/bash
# =====================================================================================
# Replication kit — run the design-pattern-composition energy bench on a SECOND machine
# to test external validity of the regime-dependent result.
#
# Prerequisites on the target machine:
#   - Linux, bare-metal (NOT a VM), Intel or AMD CPU with RAPL/powercap.
#   - .NET 8 SDK:  sudo apt install dotnet-sdk-8.0   (or https://dotnet.microsoft.com/download)
#   - Run this script from INSIDE the pattern_energy_bench folder (with Program.cs + bench.csproj).
#
# Usage:  bash run_replication.sh
# Output: repl_cpu_time.csv, repl_mem_time.csv, machine_info.txt (energie ET temps)  (+ a printed verdict).
# Send those 3 files back.
# =====================================================================================
set -e
REPS=${1:-15}                      # 15 reps (fast, enough for the large CPU effect); pass a number to change
N=200000; K=1000
LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0    # pin to the last core

echo "=== 1. Machine info ==="
{ echo "date: $(date)"; lscpu 2>/dev/null | grep -E "Model name|Architecture|^CPU\(s\)|Vendor ID"; uname -a; dotnet --version 2>/dev/null; } | tee machine_info.txt

echo "=== 2. RAPL check ==="
if [ ! -d /sys/class/powercap/intel-rapl ]; then
  echo "!! Pas de /sys/class/powercap/intel-rapl -> RAPL indisponible (VM ? AMD ?). STOP."; exit 1
fi
sudo chmod -R a+r /sys/class/powercap/intel-rapl
E=$(cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null || echo "")
[ -z "$E" ] && { echo "!! energy_uj illisible -> STOP."; exit 1; }
echo "RAPL OK (energy_uj=$E)"

echo "=== 3. Lock environment (BLOQUANT) ==="
if ! command -v cpupower >/dev/null 2>&1; then
  echo "!! cpupower ABSENT -> la frequence ne sera PAS verrouillee, la campagne serait invalide."
  echo "   Installe-le puis relance :"
  echo "     sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"
  exit 1
fi
sudo cpupower frequency-set -g performance >/dev/null 2>&1
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo >/dev/null 2>&1 || echo "(no_turbo indispo, non bloquant)"
# verification stricte : tous les coeurs doivent etre en 'performance'
BAD=$(grep -L performance /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | wc -l)
GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
if [ "$BAD" -ne 0 ] || [ "$GOV" != "performance" ]; then
  echo "!! Gouverneur = '$GOV' (attendu: performance). STOP - campagne invalide sans verrouillage."
  exit 1
fi
echo "Gouverneur verrouille: performance  |  turbo: $(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo n/a)"
export DOTNET_TieredCompilation=0
echo "core epingle = $LC"

echo "=== 4. Build + equiv ==="
dotnet build -c Release >/dev/null
BIN=./bin/Release/net8.0/proto
$BIN equiv

CFGS=$($BIN list | awk '{print $2}' | grep -v '^base$')

# extract one named field from a runk output line:  ext <field> "<line>"
ext(){ printf '%s\n' "$2" | sed -n "s/.*$1=\([0-9.]*\).*/\1/p"; }

campaign(){  # $1=regime  $2=outfile
  # NOTE: we now capture TIME as well as ENERGY, from the same runk invocation.
  # This lets us separate "the composition does more work" (time) from
  # "the composition draws more power" (energy at equal time) -- see analyse_time.py.
  echo "rep,config,e_base,e_cfg,t_base,t_cfg" > "$2"
  for r in $(seq 1 $REPS); do
    for c in $(printf "%s\n" $CFGS | shuf); do
      OB=$(taskset -c $LC $BIN runk base $1 $N $K 0)
      OC=$(taskset -c $LC $BIN runk $c   $1 $N $K 0)
      echo "$r,$c,$(ext energy_J "$OB"),$(ext energy_J "$OC"),$(ext time_s "$OB"),$(ext time_s "$OC")" >> "$2"
    done
    echo "  [$1] pass $r/$REPS ($(date +%H:%M:%S))"
  done
}
echo "=== 5. Campagne CPU (~40 min) ==="; campaign cpu repl_cpu_time.csv
echo "=== 6. Campagne MEMOIRE (~40 min) ==="; campaign mem repl_mem_time.csv

echo "=== 7. Verdict (delta des combos cles) ==="
python3 - <<'PYEOF'
import csv, statistics, math
C=["St","De","Ad","Fa","Bu","Ob","Me"]; P=lambda n:[c for c in C if c in n]
def load(f):
    d={}
    for r in csv.DictReader(open(f)):
        try: eb=float(r["e_base"]); ec=float(r["e_cfg"])
        except: continue
        if eb>0: d.setdefault(r["config"],[]).append(ec/eb)
    return d
def deltas(f):
    d=load(f); rho={k:statistics.median(v) for k,v in d.items()}
    se={k:(1.2533*statistics.pstdev(v)/math.sqrt(len(v)) if len(v)>1 else 0) for k,v in d.items()}
    sg={k:rho[k]-1 for k in C if k in rho}; out={}
    for k in rho:
        p=P(k)
        if len(p)<2 or not all(x in sg for x in p): continue
        D=rho[k]-1-sum(sg[x] for x in p); two=2*math.sqrt(se[k]**2+sum(se[x]**2 for x in p))
        out[k]=(D*100,two*100)
    return out
cpu=deltas("repl_cpu_time.csv"); mem=deltas("repl_mem_time.csv")
print("  combo      delta_CPU        delta_MEM")
for k in ["FaBuMe","BuObMe","BuMe","ObMe","FaOb","StDeAd"]:
    dc=cpu.get(k); dm=mem.get(k)
    sc=("%+5.1f%% (2SE %.1f)"%dc) if dc else "-"
    sm=("%+5.1f%% (2SE %.1f)"%dm) if dm else "-"
    print("  %-8s  %-18s %s"%(k,sc,sm))
print("\n=> ATTENDU si l'effet se replique : combos de tas TRES positifs en CPU (dizaines de %),")
print("   petits en MEMOIRE, et StDeAd (controle) ~0 dans les deux.")
PYEOF
echo "=== FINI. Renvoie : repl_cpu_time.csv, repl_mem_time.csv, machine_info.txt ==="
