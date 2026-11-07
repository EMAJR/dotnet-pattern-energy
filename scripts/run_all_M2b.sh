#!/bin/bash
# =====================================================================================
# MACHINE 2 -- second round (~3 h): old-vs-new code A/B, then a second topology campaign.
#   step 0  pre-flight checks
#   step 1  patch + build + equivalence (current code)
#   step 2  code A/B: September code vs current code, interleaved   (~1 h 45)
#   step 3  B4 topology, second campaign                              (~1 h)
#   step 4  package M2b_results_<date>.tar.gz
# Usage:  bash run_all_M2b.sh 2>&1 | tee run_all_M2b.log
# =====================================================================================
cd "$(dirname "$0")"
START=$(date +%s); STAMP=$(date +%Y%m%d); FAILED=""
say(){ echo; echo "=================== $* ($(date +%H:%M:%S)) ==================="; }
step(){ local name="$1"; shift; say "$name"; if "$@"; then echo ">> $name OK"; else echo "!! $name FAILED (continuing)"; FAILED="$FAILED $name"; fi; }

say "0. pre-flight checks"
sudo -v || { echo "!! sudo required"; exit 1; }
( while true; do sudo -n true; sleep 50; done ) 2>/dev/null & KEEP=$!
trap 'kill $KEEP 2>/dev/null' EXIT
V=$(systemd-detect-virt 2>/dev/null)
{ [ -z "$V" ] || [ "$V" = "none" ]; } || { echo "!! running inside a VM ($V) -> STOP"; exit 1; }
[ -d /sys/class/powercap/intel-rapl ] || { echo "!! no RAPL -> STOP"; exit 1; }
for t in dotnet perf cpupower python3; do command -v $t >/dev/null || { echo "!! $t missing -> STOP"; exit 1; }; done
AC=$(cat /sys/class/power_supply/A*/online 2>/dev/null | head -1)
[ "$AC" = "1" ] || { echo "!! not on AC power -> plug it in and restart"; exit 1; }
[ -f Program_septembre.cs.txt ] || { echo "!! Program_septembre.cs.txt missing -> STOP"; exit 1; }
echo "power profile: $(powerprofilesctl get 2>/dev/null || echo n/a)  (keep the same profile as last time: performance)"
echo "pre-flight OK"

say "1. patch + build + equivalence"
python3 patch_phaseB.py || exit 1
dotnet build -c Release >/dev/null || { echo "!! build failed -> STOP"; exit 1; }
./bin/Release/net8.0/proto equivtopo >/dev/null || { echo "!! equivtopo FAILED -> STOP"; exit 1; }
echo "build + equivalence OK"

INHIBIT=""
if command -v systemd-inhibit >/dev/null && systemd-inhibit --what=sleep:idle --why=test true 2>/dev/null; then
  INHIBIT="systemd-inhibit --what=sleep:idle --why=energy-bench"; fi

step "code_AB"     $INHIBIT bash run_code_ab.sh 10
step "B4_topology" $INHIBIT bash run_B4_topology.sh 8 3 cpu

say "4. packaging"
OUTD="M2b_results_$STAMP"; rm -rf "$OUTD"; mkdir -p "$OUTD"
for f in code_ab.csv code_ab_meta.txt B4_energy.csv B4_perf.csv run_all_M2b.log; do
  [ -f "$f" ] && cp "$f" "$OUTD/M2b_$f"; done
tar czf "$OUTD.tar.gz" "$OUTD"
echo; echo "DONE in $(( ( $(date +%s) - START ) / 60 )) min.  Failed steps: ${FAILED:-none}"
echo "Send back this single file:  $PWD/$OUTD.tar.gz"
