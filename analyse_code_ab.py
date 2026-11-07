import csv,statistics as st,random,sys
def dec(c): return [c[i:i+2] for i in range(0,len(c),2)]
def run(fn,lab):
    R=list(csv.DictReader(open(fn)))
    print(f"===== {lab}")
    for reg in ("cpu","mem"):
        res={}
        for v in ("old","new"):
            S=[r for r in R if r["regime"]==reg and r["version"]==v]
            D={}
            for r in S: D.setdefault(r["config"],[]).append(float(r["e_cfg"])/float(r["e_base"]))
            eb=[float(r["e_base"]) for r in S]; tb=[float(r["t_base"]) for r in S]
            res[v]=(D,st.median(eb),st.median(tb))
        print(f"-- {reg}: baseline old {res['old'][1]:.3f} J ({res['old'][2]:.3f}s)  new {res['new'][1]:.3f} J ({res['new'][2]:.3f}s)  ratio {res['new'][1]/res['old'][1]:.3f}")
        rng=random.Random(4)
        def d(D,c,r=None):
            m=(lambda x: st.median(r.choices(x,k=len(x)))) if r else st.median
            return m(D[c])-1-sum(m(D[p])-1 for p in dec(c))
        print("   singles old/new:", {p:(round(st.median(res['old'][0][p]),3),round(st.median(res['new'][0][p]),3)) for p in ["St","De","Ad","Fa","Bu","Ob","Me"]})
        for c in ["FaBuMe","BuObMe","BuMe","ObMe","FaBu","BuOb","StDeAd","StFa","StDe"]:
            Do,Dn=res['old'][0],res['new'][0]
            bo=[d(Do,c,rng) for _ in range(3000)]; bn=[d(Dn,c,rng) for _ in range(3000)]
            diff=[a-b for a,b in zip(bo,bn)]; xo,xn=d(Do,c),d(Dn,c)
            print(f"   {c:7s} old {100*xo:+6.1f} [{200*st.stdev(bo):4.1f}]  new {100*xn:+6.1f} [{200*st.stdev(bn):4.1f}]  diff {100*(xo-xn):+6.1f}  z {(xo-xn)/st.stdev(diff):+5.1f}   absJ old {xo*res['old'][1]:.2f} new {xn*res['new'][1]:.2f}")
run("/sessions/intelligent-friendly-davinci/mnt/uploads/code_ab.csv","M1")
import glob; run(glob.glob("/tmp/m2b/*/M2b_code_ab.csv")[0],"M2")
