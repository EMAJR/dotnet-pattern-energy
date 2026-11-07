import csv,statistics as st,random,math,sys
def dec(c): return [c[i:i+2] for i in range(0,len(c),2)]
def load(fn,t):
    R={}
    for r in csv.DictReader(open(fn)):
        if r["topo"]==t: R.setdefault(r["config"],[]).append(float(r["e_cfg"])/float(r["e_base"]))
    return R
def d(R,c,rng=None):
    m=(lambda v: st.median(rng.choices(v,k=len(v)))) if rng else st.median
    return m(R[c])-1-sum(m(R[p])-1 for p in dec(c))
def sig(R,c,B=10000):
    rng=random.Random(1);bs=sorted(d(R,c,rng) for _ in range(B));se=st.stdev(bs)
    a=0.05/26;lo=bs[int(a/2*B)];hi=bs[int((1-a/2)*B)-1];x=d(R,c)
    m="*" if abs(x)>3.0976*se and (lo>0 or hi<0) else ("†" if abs(x)>3.0976*se else "")
    return x,se,m
def ins(fn,t,c):
    M={}
    for r in csv.DictReader(open(fn)):
        if r["topo"]==t: M.setdefault(r["config"],[]).append((float(r["instructions"]),float(r["branch_misses"]),int(r["K"])+int(r["warmup"])))
    def s(i):
        b=st.median(x[i] for x in M["base"])
        return ((st.median(x[i] for x in M[c])-b)-sum(st.median(x[i] for x in M[p])-b for p in dec(c)))/(M[c][0][2]*200000)
    return s(0),s(1)
old=("/sessions/intelligent-friendly-davinci/mnt/caso-project (Copy)/data_campaigns/phaseB/B4_energy.csv","/sessions/intelligent-friendly-davinci/mnt/caso-project (Copy)/data_campaigns/phaseB/B4_perf.csv")
new=("/sessions/intelligent-friendly-davinci/mnt/uploads/B4_energy-63f2bdc0.csv","/sessions/intelligent-friendly-davinci/mnt/uploads/B4_perf-87194521.csv")
print("comp topo | run1 dE [2SE] instr | run2 dE [2SE] instr brmiss")
for t in "012":
  Ro,Rn=load(old[0],t),load(new[0],t)
  for c in ["FaBu","BuMe","BuOb","ObMe","FaBuMe","BuObMe","StDeAd"]:
    a=sig(Ro,c);b=sig(Rn,c);io=ins(old[1],t,c);inn=ins(new[1],t,c)
    print(f"{c:7s} {t} | {100*a[0]:+6.1f}{a[2]:1s} [{200*a[1]:4.1f}] {io[0]:5.2f} | {100*b[0]:+6.1f}{b[2]:1s} [{200*b[1]:4.1f}] {inn[0]:5.2f} {inn[1]:.4f}")
# isolated signatures run2 topo2
for t in "012":
  Rn=load(new[0],t); print(t,{p:round(st.median(Rn[p]),3) for p in ["Fa","Bu","Ob","Me","St","De","Ad"] if p in Rn})
