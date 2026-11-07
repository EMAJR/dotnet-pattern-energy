import csv,sys,statistics as st,glob
N=200000
def dec(s): return [s[i:i+2] for i in range(0,len(s),2)]
for f in sorted(glob.glob("*/kdiag_perf.csv")):
    R=list(csv.DictReader(open(f))); print("=====",f.split('/')[0])
    div=600*N
    for reg in ("cpu","mem"):
        for v in ("old","new"):
            M={}
            for r in R:
                if r["regime"]==reg and r["version"]==v: M.setdefault(r["config"],[]).append(r)
            med=lambda c,col: st.median(float(x[col]) for x in M[c])
            sd=lambda c,col: (max(float(x[col]) for x in M[c])-min(float(x[col]) for x in M[c]))/div
            print(f"{reg} {v}: base instr {med('base','instructions')/div:6.2f} cyc {med('base','cycles')/div:6.2f} (range {sd('base','cycles'):.2f}) bmiss {med('base','branch_misses')/div*1000:.3f}e-3 t {med('base','time_s'):.2f}s IPC {med('base','instructions')/med('base','cycles'):.2f}")
            line="   singles dI/dC:"
            for p in "St De Ad Fa Bu Ob Me".split():
                line+=f" {p} {(med(p,'instructions')-med('base','instructions'))/div:5.1f}/{(med(p,'cycles')-med('base','cycles'))/div:5.1f}"
            print(line)
            line="   surplus I/C:"
            for c in ("FaBuMe","BuObMe","BuMe","ObMe","StDeAd"):
                si=((med(c,"instructions")-med("base","instructions"))-sum(med(p,"instructions")-med("base","instructions") for p in dec(c)))/div
                sc=((med(c,"cycles")-med("base","cycles"))-sum(med(p,"cycles")-med("base","cycles") for p in dec(c)))/div
                rc = sc/ (med('base','cycles')/div)*100
                line+=f" {c} {si:+5.1f}/{sc:+6.1f}({rc:+.0f}%)"
            print(line)
