#!/bin/bash
# =====================================================================================
# B2 -- WHICH RUNTIME MECHANISM?  (~20 min)
#
# The article attributes the polymorphic surplus to "lost guarded devirtualization" (GDV).
# But the campaigns run with TieredCompilation=0, which disables dynamic PGO, on which GDV
# relies in .NET 8. Competing explanation: VIRTUAL STUB DISPATCH (VSD) -- an interface call
# site starts with a monomorphic dispatch stub and is back-patched to a polymorphic RESOLVE
# stub (hash lookup) once a second concrete type shows up; every call then pays the slower path.
#
# PRE-REGISTERED PREDICTIONS
#   VSD : the disassembly of RunShared contains an indirect call through a stub cell for
#         sides[s].Step (typically  mov r11, <cell> ; call [r11]) in BOTH ObMe and Bu x2, and
#         NO type-guard + inlined Step. perf attributes extra samples to stub / resolver code
#         for ObMe, not for Bu x2.
#   GDV : the TIERED (PGO) disassembly shows a method-table compare guarding an inlined or
#         direct call to the dominant Step; the default (TC=0) disassembly shows none.
#   Both can be true: VSD explains the campaigns (TC=0), GDV changes the picture in production.
#
# Usage:  bash run_B2_mechanism.sh
# Output: folder B2_out/ (disassemblies, JIT summaries, perf reports)
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
check_perf; lock_env
build_patched
build_tiered
OUTD=B2_out; rm -rf "$OUTD"; mkdir -p "$OUTD"
METHOD="ComposedTopo:RunShared"
export BENCH_WARMUP=300 BENCH_SETTLE_MS=1500

# config label | runktopo arguments (config regime n K idle topo dup rep)
SPECS="ObMe:ObMe:1 Bux2:Bu:2 BuMe:BuMe:1 Bu:Bu:1"

echo "=== 1. JIT disassembly of $METHOD (default TC=0 vs tiered+PGO) ==="
for sp in $SPECS; do
  lab=${sp%%:*}; rest=${sp#*:}; c=${rest%%:*}; d=${rest##*:}
  run_default env DOTNET_JitDisasm="$METHOD" DOTNET_JitStdOutFile="$PWD/$OUTD/disasm_default_$lab.txt" \
      taskset -c $LC $BIN   runktopo $c cpu $N 20 0 0 $d 1 > "$OUTD/run_default_$lab.txt"
  run_tiered  env DOTNET_JitDisasm="$METHOD" DOTNET_JitStdOutFile="$PWD/$OUTD/disasm_tiered_$lab.txt" \
      taskset -c $LC $BIN_T runktopo $c cpu $N 20 0 0 $d 1 > "$OUTD/run_tiered_$lab.txt"
  run_default env DOTNET_JitDisasmSummary=1 DOTNET_JitStdOutFile="$PWD/$OUTD/jitsummary_default_$lab.txt" \
      taskset -c $LC $BIN   runktopo $c cpu $N 20 0 0 $d 1 > /dev/null
  run_tiered  env DOTNET_JitDisasmSummary=1 DOTNET_JitStdOutFile="$PWD/$OUTD/jitsummary_tiered_$lab.txt" \
      taskset -c $LC $BIN_T runktopo $c cpu $N 20 0 0 $d 1 > /dev/null
  echo "  $lab : default $(wc -l < $OUTD/disasm_default_$lab.txt 2>/dev/null || echo 0) lines, tiered $(wc -l < $OUTD/disasm_tiered_$lab.txt 2>/dev/null || echo 0) lines"
done

echo "=== 2. perf record with JIT symbol maps (default TC=0) ==="
for sp in $SPECS; do
  lab=${sp%%:*}; rest=${sp#*:}; c=${rest%%:*}; d=${rest##*:}
  run_default env DOTNET_PerfMapEnabled=1 perf record -q -o "$OUTD/perf_$lab.data" -- \
      taskset -c $LC $BIN runktopo $c cpu $N 300 0 0 $d 1 > /dev/null 2>&1
  perf report -i "$OUTD/perf_$lab.data" --stdio --sort dso,symbol --percent-limit 0.3 2>/dev/null \
      | grep -v '^#' | grep -v '^$' | head -40 > "$OUTD/perfreport_$lab.txt"
  echo "  $lab : top symbols"; head -8 "$OUTD/perfreport_$lab.txt" | sed 's/^/     /'
done

echo "=== 3. quick look: call instructions in the hot loop ==="
for f in "$OUTD"/disasm_*.txt; do
  echo "--- $(basename $f): $(grep -c 'call' $f 2>/dev/null) call lines, $(grep -ciE 'r11\]|\[r11' $f 2>/dev/null) via [r11], $(grep -ciE 'cmp .*qword ptr \[r' $f 2>/dev/null) qword compares"
done
tar czf B2_out.tgz "$OUTD"
echo "=== DONE. Send me B2_out.tgz ==="
