#!/bin/bash
# =====================================================================================
# DISPATCH-SITE EXPERIMENT, v2 -- self-contained.
#
# v1 ESTABLISHED (M1_dispatch_*.csv): at an EQUAL number of independent allocating
# sources, a polymorphic shared call site costs 8.3x more than a monomorphic one.
#     Bu x2 / Me x2 / Ob x2  (2 sources, monomorphic) : +3.1 instructions per iteration
#     BuMe  / ObMe           (2 sources, POLYMORPHIC) : +25.6 instructions per iteration
#
# v1 WAS INCOMPLETE on two points, both fixed here:
#   (1) the control StDeAd had no additive prediction -- St, De and Ad were missing from
#       the configuration list. My error, not hers.
#   (2) the contrast existed only at two layers. The perf campaign showed +40.0
#       instructions per iteration at three heterogeneous layers; the monomorphic
#       counterpart at three layers (dup = 3) was never measured.
#
# THE LAW UNDER TEST
#   surplus per iteration depends on the number of DISTINCT CONCRETE TYPES at the shared
#   dispatch site sides[s].Step(i, v), not on the number of layers and not on what the
#   layers do.
#
#       layers  site           configurations          predicted surplus / iteration
#          2    monomorphic    Bu x2, Me x2, Ob x2     small   (measured: +3.1)
#          2    POLYMORPHIC    BuMe, ObMe              large   (measured: +25.6)
#          3    monomorphic    Bu x3, Me x3            small   <-- NEW, the decisive cell
#          3    POLYMORPHIC    FaBuMe                  larger  (measured: +40.0)
#          3    chain layers   StDeAd                  zero    <-- NEW, proper control
#
#   If Bu x3 and Me x3 stay small while FaBuMe is large, the law holds and the mechanism
#   is settled. If Bu x3 and Me x3 grow with the layer count, the allocation-source
#   component is larger than v1 suggested and the decomposition must be revised.
#   Both outcomes are results. Do NOT assume one.
#
# Usage:  bash run_dispatch.sh [REPS]      (default 8)
# Output: dispatch_energy.csv, dispatch_perf.csv  (+ printed verdict).  ~45 min.
# =====================================================================================
set -e
REPS=${1:-8}
N=200000
KE=1000         # energy/time campaign, paired protocol
KP=5000         # perf campaign, high K so the measured loop dominates the process
LC=$(( $(nproc) - 1 )); [ "$LC" -lt 0 ] && LC=0

# config:dup   -- isolated patterns first (they feed every additive prediction)
SPEC="St:1 De:1 Ad:1 Fa:1 Bu:1 Me:1 Ob:1 Bu:2 Me:2 Ob:2 Bu:3 Me:3 BuMe:1 ObMe:1 FaBuMe:1 StDeAd:1"

echo "=== 1. RAPL check ==="
[ -d /sys/class/powercap/intel-rapl ] || { echo "!! No intel-rapl -> STOP"; exit 1; }
sudo chmod -R a+r /sys/class/powercap/intel-rapl
cat /sys/class/powercap/intel-rapl:0/energy_uj >/dev/null || { echo "!! energy_uj unreadable -> STOP"; exit 1; }
echo "RAPL OK"

echo "=== 2. Lock environment (BLOQUANT) ==="
command -v cpupower >/dev/null 2>&1 || { echo "!! cpupower ABSENT -> STOP"; exit 1; }
sudo cpupower frequency-set -g performance >/dev/null 2>&1
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo >/dev/null 2>&1 || echo "(no_turbo indispo, non bloquant)"
BAD=$(grep -L performance /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | wc -l)
GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
[ "$BAD" -eq 0 ] && [ "$GOV" = "performance" ] || { echo "!! Gouverneur='$GOV'. STOP."; exit 1; }
export DOTNET_TieredCompilation=0
echo "gouverneur verrouille | coeur epingle = $LC | REPS=$REPS | configs=$(printf '%s\n' $SPEC | wc -l)"

echo "=== 3. Build + equiv ==="
dotnet build -c Release >/dev/null
BIN=./bin/Release/net8.0/proto
$BIN equiv

echo "=== 4. Validite de construction : dup ne doit PAS changer le checksum ==="
CSB=$(taskset -c $LC $BIN runk base cpu $N 20 0 | sed -n 's/.*checksum=\([0-9.-]*\).*/\1/p')
echo "  base              checksum=$CSB"
OKCS=1
for c in Bu Me Ob; do
  for d in 1 2 3; do
    CS=$(taskset -c $LC $BIN runkdup $c cpu $N 20 0 $d | sed -n 's/.*checksum=\([0-9.-]*\).*/\1/p')
    [ "$CS" = "$CSB" ] || OKCS=0
    echo "  $c dup=$d          checksum=$CS"
  done
done
[ "$OKCS" -eq 1 ] || { echo "!! CHECKSUM DIVERGENT -> dup change le resultat calcule. STOP."; exit 1; }
echo "  -> tous identiques. dup preserve le comportement."

echo "=== 5. Allocation : dup=m alloue-t-il bien m fois plus ? ==="
for c in Bu Me Ob; do
  L="  $c :"
  for d in 1 2 3; do
    A=$(taskset -c $LC $BIN runkdup $c cpu $N 200 0 $d | sed -n 's/.*alloc_per_iter=\([0-9]*\).*/\1/p')
    L="$L  dup=$d -> $A o/tache ;"
  done
  echo "$L"
done
echo "  -> doit croitre lineairement. C'est ce qui fait de dup un vrai multiplicateur de sources."

ext(){ printf '%s\n' "$2" | sed -n "s/.*$1=\([0-9.]*\).*/\1/p"; }

echo "=== 6. Campagne ENERGIE + TEMPS (protocole apparie, ~14 min) ==="
echo "rep,config,dup,e_base,e_cfg,t_base,t_cfg" > dispatch_energy.csv
for r in $(seq 1 $REPS); do
  for sp in $(printf "%s\n" $SPEC | shuf); do
    c=${sp%%:*}; d=${sp##*:}
    OB=$(taskset -c $LC $BIN runk base cpu $N $KE 0)
    OC=$(taskset -c $LC $BIN runkdup "$c" cpu $N $KE 0 "$d")
    echo "$r,$c,$d,$(ext energy_J "$OB"),$(ext energy_J "$OC"),$(ext time_s "$OB"),$(ext time_s "$OC")" >> dispatch_energy.csv
  done
  echo "  [energie] passe $r/$REPS ($(date +%H:%M:%S))"
done

echo "=== 7. Campagne COMPTEURS (perf, ~30 min) ==="
command -v perf >/dev/null 2>&1 || { echo "!! perf ABSENT -> on garde seulement dispatch_energy.csv"; exit 0; }
PARANOID=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo 3)
[ "$PARANOID" -gt 1 ] && echo 1 | sudo tee /proc/sys/kernel/perf_event_paranoid >/dev/null
EVENTS="cycles,instructions"
for e in L1-dcache-load-misses dTLB-load-misses page-faults; do
  perf stat -e "$e" true >/dev/null 2>&1 && EVENTS="$EVENTS,$e"
done
echo "  events: $EVENTS"

measure(){ perf stat -x, -e "$EVENTS" -- taskset -c $LC $BIN runkdup "$1" cpu $N $KP 0 "$2" 2>&1 \
    | awk -F, 'NF>=3 && $1 ~ /^[0-9]+$/ {printf "%s=%s\n",$3,$1}'; }
measure_base(){ perf stat -x, -e "$EVENTS" -- taskset -c $LC $BIN runk base cpu $N $KP 0 2>&1 \
    | awk -F, 'NF>=3 && $1 ~ /^[0-9]+$/ {printf "%s=%s\n",$3,$1}'; }
get(){ printf '%s\n' "$2" | sed -n "s/^$1=\([0-9]*\)$/\1/p" | head -1; }
emit(){ echo "$1,$2,$3,$(get cycles "$4"),$(get instructions "$4"),$(get L1-dcache-load-misses "$4"),$(get dTLB-load-misses "$4"),$(get page-faults "$4")" >> dispatch_perf.csv; }

echo "rep,config,dup,cycles,instructions,l1d_misses,dtlb_misses,page_faults" > dispatch_perf.csv
for r in $(seq 1 $REPS); do
  emit "$r" base 1 "$(measure_base)"
  for sp in $(printf "%s\n" $SPEC | shuf); do
    c=${sp%%:*}; d=${sp##*:}
    emit "$r" "$c" "$d" "$(measure "$c" "$d")"
  done
  echo "  [perf] passe $r/$REPS ($(date +%H:%M:%S))"
done

echo "=== 8. VERDICT ==="
python3 - <<'PYEOF'
import csv, statistics as st
N=200000; KP=5000
def key(r): return r["config"]+("x%s"%r["dup"] if r["dup"]!="1" else "")
# name, constituent isolated patterns, layer count, site type
TESTS=[("Bux2",["Bu"]*2,2,"monomorphe"), ("Mex2",["Me"]*2,2,"monomorphe"), ("Obx2",["Ob"]*2,2,"monomorphe"),
       ("Bux3",["Bu"]*3,3,"monomorphe"), ("Mex3",["Me"]*3,3,"monomorphe"),
       ("BuMe",["Bu","Me"],2,"POLYMORPHE"), ("ObMe",["Ob","Me"],2,"POLYMORPHE"),
       ("FaBuMe",["Fa","Bu","Me"],3,"POLYMORPHE"),
       ("StDeAd",["St","De","Ad"],3,"chaine (temoin)")]

rows=list(csv.DictReader(open("dispatch_energy.csv")))
for lbl,num,den in (("ENERGIE","e_cfg","e_base"),("TEMPS","t_cfg","t_base")):
    d={}
    for r in rows:
        try: a=float(r[num]); b=float(r[den])
        except: continue
        if b>0: d.setdefault(key(r),[]).append(a/b)
    rho={k:st.median(v) for k,v in d.items()}
    print("\n--- %s : ecart a l'additivite ---"%lbl)
    print("  %-8s %3s %-16s %9s %11s %10s"%("config","m","site","rho","rho addit.","delta"))
    for k,ps,m,site in TESTS:
        if k not in rho or not all(p in rho for p in ps): print("  %-8s  ABSENT"%k); continue
        add=1+sum(rho[p]-1 for p in ps)
        print("  %-8s %3d %-16s %9.4f %11.4f %+9.1f%%"%(k,m,site,rho[k],add,100*(rho[k]-add)))

try: rows=list(csv.DictReader(open("dispatch_perf.csv")))
except FileNotFoundError: rows=[]
if rows:
    cols=["cycles","instructions","l1d_misses","dtlb_misses"]
    D={c:{} for c in cols}
    for r in rows:
        for c in cols:
            try: D[c].setdefault(key(r),[]).append(float(r[c]))
            except: pass
    M={c:{k:st.median(v) for k,v in D[c].items() if v} for c in cols}
    b={c:M[c]["base"] for c in cols}
    print("\n--- LA LOI : surplus d'instructions par iteration du noyau ---")
    print("  (noyau de reference = %.1f instructions / iteration)"%(b["instructions"]/KP/N))
    print("  %-8s %3s %-16s %13s %13s %12s %9s"%("config","m","site","instr/tache","predit","surplus/iter","surplus%"))
    for k,ps,m,site in TESTS:
        c="instructions"
        if k not in M[c] or not all(p in M[c] for p in ps): continue
        net=(M[c][k]-b[c])/KP; pred=sum(M[c][p]-b[c] for p in ps)/KP; sur=net-pred
        print("  %-8s %3d %-16s %13.0f %13.0f %12.1f %8.1f%%"%(k,m,site,net,pred,sur/N,100*sur/pred if pred else float('nan')))
    print("\n  %-8s %10s %10s %10s %9s"%("config","d cycles","d L1D","d dTLB","IPC"))
    ipcb=b["instructions"]/b["cycles"]
    for k,ps,m,site in TESTS:
        if k not in M["cycles"]: continue
        line="  %-8s"%k
        for c in ("cycles","l1d_misses","dtlb_misses"):
            if not all(p in M[c] for p in ps): line+="%10s"%"--"; continue
            net=M[c][k]-b[c]; pred=sum(M[c][p]-b[c] for p in ps)
            line+=("%9.1f%%"%(100*(net-pred)/pred)) if abs(pred)>1 else "%10s"%"--"
        print(line+"%9.3f"%(M["instructions"][k]/M["cycles"][k]))
    print("  %-8s %10s %10s %10s %9.3f"%("base","--","--","--",ipcb))

print("""
LECTURE
  Le temoin StDeAd doit etre a ~0 sur les trois compteurs : si non, campagne a refaire.
  Bu x3 et Me x3 petits alors que FaBuMe est grand -> le surplus suit le nombre de TYPES
      au site d'appel, pas le nombre de couches. Mecanisme etabli.
  Bu x3 et Me x3 qui croissent avec m -> la composante 'sources d'allocation' est plus
      grande que ne le disait la v1, et la decomposition doit etre revue.""")
PYEOF

echo "=== FINI. Renvoie dispatch_energy.csv et dispatch_perf.csv ==="
