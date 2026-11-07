#!/bin/bash
# =====================================================================================
# MACHINE 2 -- run every pending phase-B measurement in one go, then package the results.
#
#   step 0  pre-flight checks (bare metal, RAPL, perf, cpupower, dotnet, AC power)
#   step 1  patch + build + checksum equivalence             (~3 min)
#   step 2  B0  metadata + idle power                        (~5 min)
#   step 3  B4  invocation topology (causal replication)     (~1 h)
#   step 4  replication campaign, energy AND time, cpu+mem   (~2 h 30)
#   step 5  B1  hardware counters at several weights          (~1 h)   [skip with NO_B1=1]
#   step 6  package everything as M2_results_<date>.tar.gz
#
# Usage (from inside this folder, in a terminal, laptop on AC power, lid open):
#     bash run_all_M2.sh 2>&1 | tee run_all_M2.log
# The password is asked once at the start; the script keeps sudo alive and blocks sleep.
# If one step fails, the following steps still run; the log says which one failed.
# =====================================================================================
cd "$(dirname "$0")"
START=$(date +%s)
STAMP=$(date +%Y%m%d)
FAILED=""

say(){ echo; echo "=================== $* ($(date +%H:%M:%S)) ==================="; }
step(){ local name="$1"; shift; say "$name"; if "$@"; then echo ">> $name OK"; else echo "!! $name FAILED (continuing)"; FAILED="$FAILED $name"; fi; }

# ---------- step 0: pre-flight ----------
say "0. pre-flight checks"
sudo -v || { echo "!! sudo required"; exit 1; }
( while true; do sudo -n true; sleep 50; done ) 2>/dev/null & KEEP=$!
trap 'kill $KEEP 2>/dev/null' EXIT

V=$(systemd-detect-virt 2>/dev/null)
{ [ -z "$V" ] || [ "$V" = "none" ]; } || { echo "!! running inside a VM ($V): RAPL is not meaningful -> STOP"; exit 1; }
[ -d /sys/class/powercap/intel-rapl ] || { echo "!! no RAPL (/sys/class/powercap/intel-rapl) -> STOP"; exit 1; }
command -v dotnet   >/dev/null || { echo "!! dotnet SDK 8 missing -> sudo apt install -y dotnet-sdk-8.0"; exit 1; }
command -v perf     >/dev/null || { echo "!! perf missing -> sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"; exit 1; }
command -v cpupower >/dev/null || { echo "!! cpupower missing -> sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"; exit 1; }
command -v python3  >/dev/null || { echo "!! python3 missing -> sudo apt install -y python3"; exit 1; }
AC=$(cat /sys/class/power_supply/A*/online 2>/dev/null | head -1)
[ "$AC" = "1" ] || { echo "!! laptop not on AC power (online=$AC) -> plug it in and restart"; exit 1; }
echo "bare metal, RAPL, dotnet $(dotnet --version), perf, cpupower, python3, AC power: OK"

# ---------- step 1: patch + build ----------
say "1. patch + build + equivalence"
python3 patch_phaseB.py || { echo "!! patch failed -> STOP"; exit 1; }
dotnet build -c Release >/dev/null || { echo "!! build failed -> STOP (send run_all_M2.log)"; exit 1; }
./bin/Release/net8.0/proto equiv     | tail -1
./bin/Release/net8.0/proto equiv     >/dev/null || { echo "!! equiv FAILED -> STOP"; exit 1; }
./bin/Release/net8.0/proto equivtopo | tail -1
./bin/Release/net8.0/proto equivtopo >/dev/null || { echo "!! equivtopo FAILED -> STOP"; exit 1; }

# keep the machine awake for the whole run (sleep, idle, lid)
INHIBIT=""
if command -v systemd-inhibit >/dev/null && systemd-inhibit --what=sleep:idle --why=test true 2>/dev/null; then
  INHIBIT="systemd-inhibit --what=sleep:idle --why=energy-bench"; echo "sleep inhibited during the run"
else
  echo "(!) cannot inhibit sleep automatically: disable suspend/screen lock in the settings before leaving"
fi

# ---------- steps 2-5 ----------
step "B0_metadata"   $INHIBIT bash run_B0_metadata.sh
step "B4_topology"   $INHIBIT bash run_B4_topology.sh 8 3 cpu
step "replication"   $INHIBIT bash run_replication.sh 15
if [ "${NO_B1:-0}" = "1" ]; then echo "(B1 skipped: NO_B1=1)"; else
step "B1_weights"    $INHIBIT bash run_B1_perf_weights.sh 5
fi

# ---------- step 6: package ----------
say "6. packaging"
OUTD="M2_results_$STAMP"; rm -rf "$OUTD"; mkdir -p "$OUTD"
for f in B0_meta_*.txt B0_idle_*.csv B4_energy.csv B4_perf.csv \
         repl_cpu_time.csv repl_mem_time.csv machine_info.txt B1_perf_weights.csv run_all_M2.log; do
  [ -f "$f" ] && cp "$f" "$OUTD/M2_$f"
done
ls -la "$OUTD"
tar czf "$OUTD.tar.gz" "$OUTD"
MIN=$(( ( $(date +%s) - START ) / 60 ))
echo
echo "=================================================================="
echo " DONE in $MIN min.  Failed steps: ${FAILED:-none}"
echo " Send back this single file:  $PWD/$OUTD.tar.gz"
echo "=================================================================="
