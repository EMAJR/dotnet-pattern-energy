#!/bin/bash
# =====================================================================================
# Shared helpers for the phase-B scripts. Sourced, never run directly.
# =====================================================================================

N=200000
LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0
BIN=./bin/Release/net8.0/proto

# extract key=value from a runk-style output line
ext(){ printf '%s\n' "$2" | sed -n "s/.*[ ]$1=\([-0-9.eE+naN]*\).*/\1/p" | head -1; }

lock_env(){
  command -v cpupower >/dev/null 2>&1 || {
    echo "!! cpupower ABSENT -> frequency not locked, campaign invalid."
    echo "   sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"; exit 1; }
  sudo cpupower frequency-set -g performance >/dev/null 2>&1
  echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo >/dev/null 2>&1 || echo "(no_turbo unavailable)"
  BAD=$(grep -L performance /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | wc -l)
  GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
  [ "$BAD" -eq 0 ] && [ "$GOV" = "performance" ] || { echo "!! governor='$GOV' -> STOP."; exit 1; }
  NT=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo "?")
  echo "governor=performance on every core | no_turbo=$NT | pinned core=$LC"
}

check_rapl(){
  [ -d /sys/class/powercap/intel-rapl ] || { echo "!! no intel-rapl -> STOP"; exit 1; }
  sudo chmod -R a+r /sys/class/powercap/intel-rapl* 2>/dev/null
  cat /sys/class/powercap/intel-rapl:0/energy_uj >/dev/null || { echo "!! energy_uj unreadable -> STOP"; exit 1; }
}

check_perf(){
  command -v perf >/dev/null 2>&1 || {
    echo "!! perf ABSENT.  sudo apt install -y linux-tools-common linux-tools-\$(uname -r)"; exit 1; }
  PARANOID=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo 3)
  [ "$PARANOID" -gt 1 ] && echo 1 | sudo tee /proc/sys/kernel/perf_event_paranoid >/dev/null
  EVENTS="cycles,instructions"
  for e in branches branch-misses L1-dcache-load-misses dTLB-load-misses; do
    perf stat -e "$e" true >/dev/null 2>&1 && EVENTS="$EVENTS,$e"
  done
  echo "perf events: $EVENTS"
}

# run one command under perf stat; perf output goes to $1, program stdout to $2
perf_run(){ local pf="$1" of="$2"; shift 2
  perf stat -x, -o "$pf" -e "$EVENTS" -- "$@" > "$of" 2>/dev/null; }
# read one event count from a perf -x, output file
pget(){ awk -F, -v ev="$2" '$3==ev && $1 ~ /^[0-9]+$/ {print $1; exit}' "$1"; }

# Second binary, identical source, built with the .NET 8 DEFAULT JIT policy:
# tiered compilation ON + dynamic PGO ON (the configuration used in production).
# Built in a separate folder so it can never overwrite the campaign binary.
TDIR=/tmp/bench_tiered
BIN_T=$TDIR/bin/Release/net8.0/proto
build_tiered(){
  rm -rf "$TDIR"; mkdir -p "$TDIR"; cp Program.cs bench.csproj "$TDIR"/
  (cd "$TDIR" && dotnet build -c Release -p:TieredCompilation=true -p:TieredPGO=true >/dev/null) \
    || { echo "!! tiered build failed -> STOP"; exit 1; }
  RC="$TDIR/bin/Release/net8.0/proto.runtimeconfig.json"
  if grep -q '"System.Runtime.TieredCompilation": false' "$RC"; then
    echo "!! tiered binary still has TieredCompilation=false -> STOP"; cat "$RC"; exit 1; fi
  echo "tiered runtimeconfig:"; grep -E 'Tiered|PGO' "$RC" || echo "  (no explicit Tiered* entry -> runtime defaults: tiering ON, PGO ON)"
  env -u DOTNET_TieredCompilation $BIN_T equivtopo >/dev/null || { echo "!! equivtopo FAILED (tiered) -> STOP"; exit 1; }
}
# run helpers: campaign configuration vs .NET default configuration
run_default(){ env DOTNET_TieredCompilation=0 "$@"; }
run_tiered(){  env -u DOTNET_TieredCompilation DOTNET_TieredPGO=1 "$@"; }

build_patched(){
  grep -q runktopo Program.cs || { echo "!! Program.cs not patched -> run: python3 patch_phaseB.py"; exit 1; }
  dotnet build -c Release >/dev/null || { echo "!! build failed -> STOP and send me the error"; exit 1; }
  $BIN equiv >/dev/null || { echo "!! equiv FAILED -> STOP"; exit 1; }
  $BIN equivtopo | tail -1
  $BIN equivtopo >/dev/null || { echo "!! equivtopo FAILED -> STOP"; exit 1; }
}
