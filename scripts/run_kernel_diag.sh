#!/bin/bash
# =====================================================================================
# KERNEL DIAGNOSIS -- why do two functionally identical kernels give different energies? (~30 min)
#
# The A/B experiment showed that the September kernel and the current kernel (extra loop-count
# field, loop body never executed) give different interaction magnitudes (M1 compute: FaBuMe
# +100 vs +62.5) and different memory-bound baselines (M2: 15.5 s vs 3.8 s). This script does
# NOT measure energy. It answers three questions on the SAME machine, SAME build stack:
#
#   D1  code generation : JIT disassembly of KernelCpu.Compute, KernelMem.Compute, Composed.Run
#                         for both versions (same configuration as the campaigns: TC=0)
#   D2  code placement  : start address and size of these methods (runtime perf map),
#                         i.e. their alignment modulo 32 / 64 bytes
#   D3  work vs timing  : retired instructions, cycles and branch misses per iteration for the
#                         base, the 7 patterns and the key compositions, both versions, both regimes
#
# PRE-REGISTERED READINGS (do not edit after the run)
#   R1  same instruction surplus (FaBuMe ~39 instr/iter in both versions), different cycles
#         -> the shift is a timing / code-placement effect, not extra work (same as B1)
#   R2  different instruction surplus
#         -> the code change alters the work executed; D1 shows where
#   R3  memory-bound kernel: different instruction count or code for the index / bounds check
#         -> code generation explains the factor in memory-bound time
#
# Usage:  bash run_kernel_diag.sh [REPS]      (default 3)
# Needs:  Program_septembre.cs.txt and Program.cs in this folder
# Output: kdiag_<host>.tgz
# =====================================================================================
cd "$(dirname "$0")"
source ./phaseB_common.sh
REPS=${1:-3}
H=$(hostname -s); OUTD="kdiag_$H"; rm -rf "$OUTD"; mkdir -p "$OUTD"
[ -f Program_septembre.cs.txt ] || { echo "!! Program_septembre.cs.txt missing -> STOP"; exit 1; }
check_perf; lock_env
export DOTNET_TieredCompilation=0

build_version(){  # $1 label, $2 source
  local d=/tmp/bench_code_$1
  rm -rf "$d"; mkdir -p "$d"; cp bench.csproj "$d"/; cp "$2" "$d"/Program.cs
  (cd "$d" && dotnet build -c Release >/dev/null) || { echo "!! build $1 failed -> STOP"; exit 1; }
  "$d"/bin/Release/net8.0/proto equiv >/dev/null || { echo "!! equiv $1 failed -> STOP"; exit 1; }
}
build_version old Program_septembre.cs.txt
build_version new Program.cs
OLD=/tmp/bench_code_old/bin/Release/net8.0/proto
NEW=/tmp/bench_code_new/bin/Release/net8.0/proto
METHODS="KernelCpu:Compute KernelMem:Compute Composed:Run"

echo "=== D1 + D2: disassembly and code placement ==="
for v in old new; do
  B=$OLD; [ "$v" = new ] && B=$NEW
  for reg in cpu mem; do
    for c in base FaBuMe; do
      tag="${v}_${reg}_${c}"
      rm -f /tmp/perf-*.map
      DOTNET_JitDisasm="$METHODS" DOTNET_JitDisasmSummary=0 DOTNET_JitStdOutFile="$PWD/$OUTD/asm_$tag.txt" \
      DOTNET_PerfMapEnabled=3 taskset -c $LC $B runk $c $reg $N 5 0 > "$OUTD/run_$tag.txt" 2>&1
      grep -hE "KernelCpu::Compute|KernelMem::Compute|Composed::Run" /tmp/perf-*.map > "$OUTD/addr_$tag.txt" 2>/dev/null
    done
  done
  echo "  $v: $(ls $OUTD/asm_${v}_* | wc -l) disassemblies"
done
python3 - "$OUTD" <<'PYEOF'
import glob, os, sys
d = sys.argv[1]
print("start address mod 32 / mod 64 and size of each method:")
for f in sorted(glob.glob(os.path.join(d, "addr_*.txt"))):
    for line in open(f):
        p = line.split(None, 2)
        if len(p) < 3: continue
        a, s = int(p[0], 16), int(p[1], 16)
        print(f"  {os.path.basename(f)[5:-4]:22s} {p[2].strip()[:60]:60s} mod32={a % 32:2d} mod64={a % 64:2d} size={s}")
PYEOF

echo "=== D3: hardware counters, both versions, both regimes ==="
CFGS="base St De Ad Fa Bu Ob Me FaBuMe BuObMe BuMe ObMe StDeAd"
K=500; TMP=$(mktemp -d)
OUT="$OUTD/kdiag_perf.csv"
echo "rep,version,regime,config,K,warmup,cycles,instructions,branches,branch_misses,time_s" > "$OUT"
for r in $(seq 1 $REPS); do
  for item in $( (for v in old new; do for reg in cpu mem; do for c in $CFGS; do echo "$v:$reg:$c"; done; done; done) | shuf); do
    IFS=: read v reg c <<< "$item"; B=$OLD; [ "$v" = new ] && B=$NEW
    perf_run "$TMP/p" "$TMP/o" taskset -c $LC $B runk $c $reg $N $K 0
    O=" $(cat $TMP/o)"
    echo "$r,$v,$reg,$c,$K,100,$(pget $TMP/p cycles),$(pget $TMP/p instructions),$(pget $TMP/p branches),$(pget $TMP/p branch-misses),$(ext time_s "$O")" >> "$OUT"
  done
  echo "  pass $r/$REPS ($(date +%H:%M:%S))"
done
rm -rf "$TMP"

echo "=== SUMMARY ==="
python3 - "$OUT" <<'PYEOF'
import csv, sys, statistics as st
R = list(csv.DictReader(open(sys.argv[1]))); N = 200000
def dec(s): return [s[i:i+2] for i in range(0, len(s), 2)]
for reg in ("cpu", "mem"):
    for v in ("old", "new"):
        M = {}
        for r in R:
            if r["regime"] == reg and r["version"] == v:
                M.setdefault(r["config"], []).append(r)
        div = (int(R[0]["K"]) + 100) * N
        med = lambda c, col: st.median(float(x[col]) for x in M[c])
        line = f"{reg} {v}: base {med('base','instructions')/div:6.1f} instr/it {med('base','cycles')/div:6.1f} cyc/it |"
        for c in ("FaBuMe", "BuMe", "StDeAd"):
            si = ((med(c,"instructions")-med("base","instructions")) - sum(med(p,"instructions")-med("base","instructions") for p in dec(c))) / div
            sc = ((med(c,"cycles")-med("base","cycles")) - sum(med(p,"cycles")-med("base","cycles") for p in dec(c))) / div
            line += f" {c} +{si:5.1f} instr {sc:+6.1f} cyc |"
        print(line)
print("\nR1: same instr surplus, different cycles | R2: different instr surplus | R3: mem kernel differs")
PYEOF
tar czf "$OUTD.tgz" "$OUTD"
echo "=== DONE. Send me $OUTD.tgz ==="
