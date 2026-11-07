#!/bin/bash
# =====================================================================================
# CODE A/B -- does the September code version change the measurements?  (~1 h 45)
#
# The campaign of record (September) ran Program_septembre.cs.txt; every later campaign ran the
# current Program.cs, whose kernel has an extra loop-count field (inactive at weight 1).
# Code version, runtime/kernel versions and date changed together, so the shift between
# September and October cannot be attributed. This experiment builds BOTH versions on the
# SAME machine, SAME day, SAME software stack, and interleaves them run by run.
#
# PRE-REGISTERED OUTCOMES (both are results; do not edit after the run)
#   C1  old and new code give the same baseline energy and the same deltas (within 2 SE)
#         -> the code change is not responsible; the September/October shift comes from the
#            software stack or from the date (campaign effect).
#   C2  they differ (baseline energy and/or deltas, especially under W_MEM)
#         -> an inactive code change in the kernel shifts the measurements: the campaign of
#            record is not comparable to the later ones, and this is itself a metrology result.
#
# Usage:  bash run_code_ab.sh [REPS]        (default 10)
# Needs:  Program_septembre.cs.txt in this folder (old version), Program.cs (current version)
# Output: code_ab.csv, code_ab_meta.txt
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
REPS=${1:-10}
K=1000
CFGS="St De Ad Fa Bu Ob Me FaBuMe BuObMe BuMe ObMe FaBu BuOb StDeAd StFa StDe"
[ -f Program_septembre.cs.txt ] || { echo "!! Program_septembre.cs.txt missing -> STOP"; exit 1; }

check_rapl; lock_env
export DOTNET_TieredCompilation=0

build_version(){  # $1 = label, $2 = source file
  local d=/tmp/bench_code_$1
  rm -rf "$d"; mkdir -p "$d"; cp bench.csproj "$d"/; cp "$2" "$d"/Program.cs
  (cd "$d" && dotnet build -c Release >/dev/null) || { echo "!! build $1 failed -> STOP"; exit 1; }
  "$d"/bin/Release/net8.0/proto equiv | tail -1
  "$d"/bin/Release/net8.0/proto equiv >/dev/null || { echo "!! equiv $1 failed -> STOP"; exit 1; }
}
build_version old Program_septembre.cs.txt
build_version new Program.cs
OLD=/tmp/bench_code_old/bin/Release/net8.0/proto
NEW=/tmp/bench_code_new/bin/Release/net8.0/proto

{ echo "date: $(date -Is)"; uname -r; dotnet --version; dotnet --list-runtimes | grep NETCore
  echo "governor=$(cat /sys/devices/system/cpu/cpu$LC/cpufreq/scaling_governor) max=$(cat /sys/devices/system/cpu/cpu$LC/cpufreq/scaling_max_freq) no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null)"
  (powerprofilesctl get 2>/dev/null || echo "powerprofilesctl n/a")
  sha256sum Program_septembre.cs.txt Program.cs; } > code_ab_meta.txt

OUT=code_ab.csv
echo "rep,version,regime,config,e_base,e_cfg,t_base,t_cfg" > "$OUT"
for r in $(seq 1 $REPS); do
  for reg in cpu mem; do
    for item in $( (for v in old new; do for c in $CFGS; do echo "$v:$c"; done; done) | shuf); do
      v=${item%%:*}; c=${item#*:}; B=$OLD; [ "$v" = new ] && B=$NEW
      OB=" $(taskset -c $LC $B runk base $reg $N $K 0)"
      OC=" $(taskset -c $LC $B runk $c $reg $N $K 0)"
      echo "$r,$v,$reg,$c,$(ext energy_J "$OB"),$(ext energy_J "$OC"),$(ext time_s "$OB"),$(ext time_s "$OC")" >> "$OUT"
    done
  done
  echo "  pass $r/$REPS ($(date +%H:%M:%S))"
done

echo "=== SUMMARY (full analysis on my side) ==="
python3 - "$OUT" <<'PYEOF'
import csv, sys, statistics as st
R = list(csv.DictReader(open(sys.argv[1])))
def dec(s): return [s[i:i+2] for i in range(0, len(s), 2)]
for reg in ("cpu", "mem"):
    print(f"--- {reg}")
    for v in ("old", "new"):
        S = [r for r in R if r["regime"] == reg and r["version"] == v]
        eb = st.median(float(r["e_base"]) for r in S)
        rho = {}
        for r in S: rho.setdefault(r["config"], []).append(float(r["e_cfg"]) / float(r["e_base"]))
        rho = {k: st.median(x) for k, x in rho.items()}
        line = f"  {v}: baseline {eb:7.3f} J"
        for c in ("FaBuMe", "BuObMe", "BuMe", "StDeAd"):
            d = rho[c] - 1 - sum(rho[p] - 1 for p in dec(c))
            line += f"  {c} {100*d:+6.1f}"
        print(line)
print("\nC1: old == new (within noise)  |  C2: old != new")
PYEOF
echo "=== DONE: code_ab.csv, code_ab_meta.txt ==="
