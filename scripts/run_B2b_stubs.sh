#!/bin/bash
# =====================================================================================
# B2b -- ATTRIBUTE HARDWARE SAMPLES TO THE DISPATCH STUBS  (~15 min, Machine 1)
#
# In B2, perf could not resolve JIT code: .NET 8 maps JIT code twice (write-xor-execute,
# "memfd:doublemapper"), so samples landed in an anonymous mapping without symbols.
# The article therefore says the stub-level mechanism is "inferred rather than observed".
# Here W^X is disabled (DOTNET_EnableWriteXorExecute=0) and the runtime writes a perf map,
# so samples in JIT code and, if the runtime logs them, in VSD stubs get names.
#
# PRE-REGISTERED PREDICTIONS (do not edit after the run)
#   P1  ObMe (polymorphic site): a visible share of samples in RESOLVE-stub code
#       (symbol containing "Resolve", or VSD/stub names), absent or much smaller for Bu x2.
#   P2  Bu x2 (monomorphic site): stub samples, if any, in DISPATCH-stub code only.
#   P3  StDeAd control: no stub samples beyond Bu (single-layer) level.
#   If stubs stay unnamed, compare the share of UNRESOLVED samples in the JIT region between
#   ObMe and Bu x2 instead; report it as such.
#   Caveat: disabling W^X changes code mapping, so timings here are not campaign timings.
#
# Usage:  bash run_B2b_stubs.sh          Output: B2b_out.tgz
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
check_perf; lock_env
build_patched
OUTD=B2b_out; rm -rf "$OUTD"; mkdir -p "$OUTD"
export DOTNET_TieredCompilation=0 DOTNET_EnableWriteXorExecute=0 DOTNET_PerfMapEnabled=1 \
       DOTNET_PerfMapShowOptimizationTiers=1 BENCH_WARMUP=300 BENCH_SETTLE_MS=1500

# label:config:dup
SPECS="ObMe:ObMe:1 Bux2:Bu:2 Bu:Bu:1 BuMe:BuMe:1 StDeAd:StDeAd:1"
for rep in 1 2 3; do
  for sp in $SPECS; do
    lab=${sp%%:*}; rest=${sp#*:}; c=${rest%%:*}; d=${rest##*:}
    perf record -q -F 4999 -o "$OUTD/perf_${lab}_$rep.data" -- \
        taskset -c $LC $BIN runktopo $c cpu $N 300 0 0 $d 1 > "$OUTD/run_${lab}_$rep.txt" 2>&1
    perf report -i "$OUTD/perf_${lab}_$rep.data" --stdio --sort symbol --percent-limit 0.1 2>/dev/null \
        | grep -v '^#' | grep -v '^$' > "$OUTD/sym_${lab}_$rep.txt"
    perf report -i "$OUTD/perf_${lab}_$rep.data" --stdio --sort dso --percent-limit 0.1 2>/dev/null \
        | grep -v '^#' | grep -v '^$' > "$OUTD/dso_${lab}_$rep.txt"
    STUB=$(grep -iE 'stub|resolve|vsd|dispatch' "$OUTD/sym_${lab}_$rep.txt" | awk '{s+=$1} END {printf "%.2f", s+0}')
    UNRES=$(grep -E '0x[0-9a-f]{8,}' "$OUTD/sym_${lab}_$rep.txt" | awk '{s+=$1} END {printf "%.2f", s+0}')
    echo "  rep $rep  $lab : stub-named samples ${STUB}%   unresolved-address samples ${UNRES}%"
  done
done
ls /tmp/perf-*.map >/dev/null 2>&1 && grep -hiE 'stub|resolve' /tmp/perf-*.map | head -50 > "$OUTD/perfmap_stub_names.txt"
rm -f "$OUTD"/*.data
tar czf B2b_out.tgz "$OUTD"
echo "=== DONE. Send me B2b_out.tgz ==="
