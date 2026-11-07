#!/bin/bash
# =====================================================================================
# B0 -- MACHINE METADATA + IDLE POWER  (~5 min)
#
# Answers the reviewer's metrology questions with facts instead of claims:
#   - which RAPL domains exist, and which ones the bench actually reads
#     (the Rapl class only scans TOP-LEVEL zones named package* or dram; sub-zones such as
#      intel-rapl:0:2 are never read -> on these laptops the metric is PACKAGE ONLY)
#   - frequency policy really in force (governor, no_turbo, min/max), SMT state
#   - exact .NET runtime/SDK, kernel, GC mode, runtimeconfig of the binary
#   - virtualisation, temperature
#   - idle package power, measured 3 x 60 s with the same locking as the campaigns
#     (needed to rebuild RQ3 with justified P_idle values)
#
# Usage:  bash run_B0_metadata.sh          Output: B0_meta_<host>.txt, B0_idle_<host>.csv
# Run it on BOTH machines.
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
H=$(hostname -s); OUT="B0_meta_${H}.txt"; IDLE="B0_idle_${H}.csv"

check_rapl
lock_env
dotnet build -c Release >/dev/null || { echo "!! build failed -> STOP"; exit 1; }

{
echo "### date";            date -Is
echo "### host / kernel";   hostname; uname -a
echo "### os";              grep -E '^(NAME|VERSION)=' /etc/os-release
echo "### virtualisation";  (systemd-detect-virt 2>/dev/null; true)
echo "### cpu";             lscpu | grep -E 'Model name|^CPU\(s\)|Thread|Core|Socket|MHz|L1d|L2|L3'
echo "### smt";             cat /sys/devices/system/cpu/smt/active 2>/dev/null || echo "?"
echo "### frequency policy (cpu0 and pinned core $LC)"
for c in 0 $LC; do d=/sys/devices/system/cpu/cpu$c/cpufreq
  echo "cpu$c governor=$(cat $d/scaling_governor) min=$(cat $d/scaling_min_freq) max=$(cat $d/scaling_max_freq) hw_max=$(cat $d/cpuinfo_max_freq) cur=$(cat $d/scaling_cur_freq)"; done
echo "intel_pstate status=$(cat /sys/devices/system/cpu/intel_pstate/status 2>/dev/null) no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null) min_perf_pct=$(cat /sys/devices/system/cpu/intel_pstate/min_perf_pct 2>/dev/null) max_perf_pct=$(cat /sys/devices/system/cpu/intel_pstate/max_perf_pct 2>/dev/null)"
echo "### RAPL zones present (all levels)"
for z in /sys/class/powercap/intel-rapl*; do
  [ -f "$z/name" ] && echo "$(basename $z)  name=$(cat $z/name)  energy_uj=$([ -r $z/energy_uj ] && echo readable || echo NOT-readable)"; done
echo "### RAPL zones READ BY THE BENCH (top level, name package* or dram)"
for z in /sys/class/powercap/intel-rapl/*/; do
  [ -f "$z/name" ] || continue; nm=$(cat $z/name)
  case "$nm" in package*|dram) echo "READ: $(basename $z) name=$nm";; *) echo "skip: $(basename $z) name=$nm";; esac; done
echo "### memory subsystem (the memory-bound baseline changed by 21 % between two M1 campaigns)"
echo "THP enabled=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null) defrag=$(cat /sys/kernel/mm/transparent_hugepage/defrag 2>/dev/null)"
grep -E 'MemTotal|HugePages_Total|Hugepagesize' /proc/meminfo
(sudo dmidecode -t memory 2>/dev/null | grep -E 'Speed|Configured' | sort -u | head -4) || true
echo "mitigations: $(cat /sys/devices/system/cpu/vulnerabilities/* 2>/dev/null | sort | uniq -c | tr '\n' ';')"
echo "### dotnet";          dotnet --version; dotnet --list-runtimes
echo "### runtimeconfig of the binary"; cat ./bin/Release/net8.0/proto.runtimeconfig.json
echo "### DOTNET_ environment"; env | grep '^DOTNET_' || echo "(none)"
echo "### temperature";     (sensors 2>/dev/null | grep -iE 'package|core 0|temp1' | head -5) || true
for t in /sys/class/thermal/thermal_zone*/; do echo "$(cat $t/type 2>/dev/null)=$(cat $t/temp 2>/dev/null)"; done | head -6
} > "$OUT" 2>&1
echo "metadata -> $OUT"

echo "### idle package power, 3 x 60 s (do not touch the machine)"
echo "run,energy_J,time_s,idle_power_W" > "$IDLE"
for r in 1 2 3; do
  sleep 10
  O=$(taskset -c $LC $BIN idle 60)
  echo "$r,$(ext energy_J " $O"),$(ext time_s " $O"),$(ext idle_power_W " $O")" >> "$IDLE"
  echo "  idle run $r: $O"
done
echo "### temperature after" >> "$OUT"
for t in /sys/class/thermal/thermal_zone*/; do echo "$(cat $t/type 2>/dev/null)=$(cat $t/temp 2>/dev/null)"; done | head -6 >> "$OUT"
echo "=== DONE. Send me $OUT and $IDLE ==="
