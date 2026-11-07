#!/usr/bin/env python3
# =====================================================================================
# Idempotent patch for the phase-B experiments. Adds, WITHOUT touching any existing code path:
#
#   class ComposedTopo      invocation topology orthogonal to the pattern type
#       topo 0 : every side layer invoked through ONE shared interface call site
#                sides[s].Step(i, v)                      (same logic as Composed; dup supported)
#       topo 1 : each side layer invoked through ITS OWN interface call site
#                (one ISide field per slot) -> every site is monomorphic, still interface dispatch
#       topo 2 : each side layer invoked through a field of its SEALED concrete type
#                -> direct call, no interface dispatch at all
#   verb  runktopo <config> <cpu|mem> <n> <K> <idle_W> <topo> <dup> <rep>
#   verb  equivtopo           checksum equivalence for every config x topo (x dup for topo 0)
#   env   BENCH_WARMUP      warm-up tasks before measuring        (default 100, as runk)
#   env   BENCH_SETTLE_MS   sleep after warm-up, then 100 more tasks (default 0) -- lets the
#                           tiered JIT finish background recompilation (experiment B3)
#   output adds  topo= dup= warmup= jit_during= jit_total=
#         jit_during = methods JIT-compiled INSIDE the measured window. It must be 0, otherwise
#         the window still contained compilation and the run is not steady state.
#
# runk, runkdup, matrixk, equiv and MeasureK are left byte-for-byte unchanged, so every
# existing campaign and script stays valid.
#
# Usage:  python3 patch_phaseB.py      (from the folder containing Program.cs)
# =====================================================================================
import sys, pathlib

p = pathlib.Path("Program.cs")
if not p.exists():
    sys.exit("!! Program.cs not found. Run this from the pattern_energy_bench folder.")
src = p.read_text(encoding="utf-8")

if "runktopo" in src:
    print("Program.cs already patched for phase B (runktopo present). Nothing to do.")
    sys.exit(0)

CLASS = r'''// ============================ Phase B: invocation topology (orthogonal to pattern type) ============================
// topo 0 : all side layers invoked through ONE shared interface call site sides[s].Step(i, v)
//          (same logic as Composed; dup > 1 replicates each layer as independent instances)
// topo 1 : each side layer invoked through ITS OWN interface call site (one ISide field per slot)
//          -> each site sees a single concrete type per run: monomorphic, still interface dispatch
// topo 2 : each side layer invoked through a field of its SEALED concrete type -> direct call,
//          no interface dispatch (strongest form of the "dedicated call site" guideline)
// The functional result still comes ONLY from chain.Compute(i): checksums are unchanged.
sealed class ComposedTopo {
    readonly ICompute chain; readonly int block; readonly int topo;
    readonly ISide[] sides;                                   // topo 0
    readonly ISide d0, d1, d2, d3;                            // topo 1
    readonly FactoryLayer tfa; readonly BuilderLayer tbu;     // topo 2
    readonly ObserverLayer tob; readonly MementoLayer tme;    // topo 2
    public ComposedTopo(int mask, bool mem, double[] buf, int block, int snapLen, int rep, int dup, int topo) {
        this.block = block; this.topo = topo;
        ICompute k = mem ? (ICompute)new KernelMem(buf, rep) : new KernelCpu(rep);
        if (Has(mask, Pat.Adapter)) k = new AdapterLayer(k);
        if (Has(mask, Pat.Decorator)) k = new DecoratorLayer(k);
        if (Has(mask, Pat.Strategy)) k = new StrategyLayer(k);
        chain = k;
        var s = new List<ISide>();
        int copies = (topo == 0 && dup > 1) ? dup : 1;
        for (int d = 0; d < copies; d++) {
            if (Has(mask, Pat.Factory)) s.Add(new FactoryLayer());
            if (Has(mask, Pat.Builder)) s.Add(new BuilderLayer());
            if (Has(mask, Pat.Observer)) s.Add(new ObserverLayer());
            if (Has(mask, Pat.Memento)) s.Add(new MementoLayer(snapLen));
        }
        sides = s.ToArray();
        if (topo == 1) {
            d0 = s.Count > 0 ? s[0] : null; d1 = s.Count > 1 ? s[1] : null;
            d2 = s.Count > 2 ? s[2] : null; d3 = s.Count > 3 ? s[3] : null;
        }
        if (topo == 2) {
            foreach (var x in s) {
                if (x is FactoryLayer fx) tfa = fx;
                else if (x is BuilderLayer bx) tbu = bx;
                else if (x is ObserverLayer ox) tob = ox;
                else if (x is MementoLayer mx) tme = mx;
            }
        }
    }
    static bool Has(int mask, int p) => (mask & (1 << p)) != 0;
    public double Run(int n) => topo == 0 ? RunShared(n) : (topo == 1 ? RunDedicated(n) : RunTyped(n));

    double RunShared(int n) {
        double acc = 0; int c = 0, b = 0;
        for (int s = 0; s < sides.Length; s++) sides[s].BlockStart(0);
        for (int i = 0; i < n; i++) {
            double v = chain.Compute(i);
            for (int s = 0; s < sides.Length; s++) sides[s].Step(i, v);
            acc += v;
            if (++c == block) { for (int s = 0; s < sides.Length; s++) sides[s].BlockEnd(b); b++; c = 0; for (int s = 0; s < sides.Length; s++) sides[s].BlockStart(b); }
        }
        if (c > 0) for (int s = 0; s < sides.Length; s++) sides[s].BlockEnd(b);
        return acc;
    }

    double RunDedicated(int n) {
        double acc = 0; int c = 0, b = 0;
        StartDedicated(0);
        for (int i = 0; i < n; i++) {
            double v = chain.Compute(i);
            if (d0 != null) d0.Step(i, v);
            if (d1 != null) d1.Step(i, v);
            if (d2 != null) d2.Step(i, v);
            if (d3 != null) d3.Step(i, v);
            acc += v;
            if (++c == block) { EndDedicated(b); b++; c = 0; StartDedicated(b); }
        }
        if (c > 0) EndDedicated(b);
        return acc;
    }
    void StartDedicated(int b) { if (d0 != null) d0.BlockStart(b); if (d1 != null) d1.BlockStart(b); if (d2 != null) d2.BlockStart(b); if (d3 != null) d3.BlockStart(b); }
    void EndDedicated(int b)   { if (d0 != null) d0.BlockEnd(b);   if (d1 != null) d1.BlockEnd(b);   if (d2 != null) d2.BlockEnd(b);   if (d3 != null) d3.BlockEnd(b); }

    double RunTyped(int n) {
        double acc = 0; int c = 0, b = 0;
        StartTyped(0);
        for (int i = 0; i < n; i++) {
            double v = chain.Compute(i);
            if (tfa != null) tfa.Step(i, v);
            if (tbu != null) tbu.Step(i, v);
            if (tob != null) tob.Step(i, v);
            if (tme != null) tme.Step(i, v);
            acc += v;
            if (++c == block) { EndTyped(b); b++; c = 0; StartTyped(b); }
        }
        if (c > 0) EndTyped(b);
        return acc;
    }
    void StartTyped(int b) { if (tfa != null) tfa.BlockStart(b); if (tbu != null) tbu.BlockStart(b); if (tob != null) tob.BlockStart(b); if (tme != null) tme.BlockStart(b); }
    void EndTyped(int b)   { if (tfa != null) tfa.BlockEnd(b);   if (tbu != null) tbu.BlockEnd(b);   if (tob != null) tob.BlockEnd(b);   if (tme != null) tme.BlockEnd(b); }
}

'''

VERBS = r'''        if (args.Length == 9 && args[0] == "runktopo") {
            int mask = Configs.FromName(args[1]); bool mem = args[2] == "mem";
            int n = int.Parse(args[3], ci); long K = long.Parse(args[4], ci); double idleW = double.Parse(args[5], ci);
            int topo = int.Parse(args[6], ci); int dup = int.Parse(args[7], ci); int rep = int.Parse(args[8], ci);
            if (topo < 0 || topo > 2) { Console.Error.WriteLine("topo must be 0, 1 or 2"); return 2; }
            if (topo != 0 && dup != 1) { Console.Error.WriteLine("dup > 1 is only defined for topo 0"); return 2; }
            int warm = EnvInt("BENCH_WARMUP", 100), settle = EnvInt("BENCH_SETTLE_MS", 0);
            long jd, jt;
            var r = MeasureKTopo(mask, mem, n, K, idleW, rep, dup, topo, warm, settle, out jd, out jt);
            Console.WriteLine(Format(r) + string.Format(ci, " topo={0} dup={1} warmup={2} settle_ms={3} jit_during={4} jit_total={5}", topo, dup, warm, settle, jd, jt));
            return 0;
        }
        if (args.Length == 1 && args[0] == "equivtopo") return EquivTopo();
'''

METHODS = r'''    // ---- Phase B: same protocol as MeasureK, on ComposedTopo, with a configurable warm-up and a
    //      count of methods JIT-compiled inside the measured window (must be 0 at steady state).
    static Res MeasureKTopo(int mask, bool mem, int n, long K, double idleW, int rep, int dup, int topo,
                            int warm, int settleMs, out long jitDuring, out long jitTotal) {
        double[] buf = mem ? new double[MEMBUF] : null;
        var comp = new ComposedTopo(mask, mem, buf, BLOCK, SNAP, rep, dup, topo);
        for (int w = 0; w < warm; w++) comp.Run(n);
        if (settleMs > 0) { Thread.Sleep(settleMs); for (int w = 0; w < 100; w++) comp.Run(n); }
        GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
        var rapl = new Rapl(); if (rapl.Available) rapl.ReadDeltaJoules();
        long a0 = GC.GetTotalAllocatedBytes(true);
        int g0 = GC.CollectionCount(0), g1 = GC.CollectionCount(1), g2 = GC.CollectionCount(2);
        TimeSpan p0 = GC.GetTotalPauseDuration();
        long j0 = System.Runtime.JitInfo.GetCompiledMethodCount(false);
        var sw = Stopwatch.StartNew(); double sink = 0;
        for (long i = 0; i < K; i++) sink += comp.Run(n);
        sw.Stop();
        double energy = rapl.Available ? rapl.ReadDeltaJoules() : double.NaN;
        long j1 = System.Runtime.JitInfo.GetCompiledMethodCount(false);
        jitDuring = j1 - j0; jitTotal = j1;
        double t = sw.Elapsed.TotalSeconds;
        double pauseMs = (GC.GetTotalPauseDuration() - p0).TotalMilliseconds;
        long alloc = GC.GetTotalAllocatedBytes(true) - a0;
        double dyn = energy - idleW * t;
        return new Res {
            mask = mask, mem = mem, K = K, rep = rep, time = t, energy = energy, power = energy / t,
            jdyn = dyn / K, checksum = sink / K, allocPerIter = alloc / Math.Max(1, K), pauseMs = pauseMs,
            g0 = GC.CollectionCount(0) - g0, g1 = GC.CollectionCount(1) - g1, g2 = GC.CollectionCount(2) - g2
        };
    }

    static int EnvInt(string name, int dflt) {
        string s = Environment.GetEnvironmentVariable(name);
        int v;
        return (s != null && int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out v) && v >= 0) ? v : dflt;
    }

    // Every configuration, under every topology (and dup 1..3 for topo 0), must reproduce the
    // baseline checksum exactly: topology changes HOW layers are invoked, never WHAT is computed.
    static int EquivTopo() {
        int n = 100000; bool ok = true; int checked_ = 0;
        foreach (bool mem in new[] { false, true }) {
            double[] buf = mem ? new double[MEMBUF] : null;
            double baseVal = new Composed(0, mem, buf, BLOCK, SNAP, 1).Run(n);
            foreach (var mask in Configs.All())
                for (int topo = 0; topo <= 2; topo++)
                    for (int dup = 1; dup <= (topo == 0 ? 3 : 1); dup++) {
                        double v = new ComposedTopo(mask, mem, buf, BLOCK, SNAP, 1, dup, topo).Run(n);
                        bool eq = Math.Abs(v - baseVal) < 1e-6; ok &= eq; checked_++;
                        if (!eq) Console.WriteLine("[{0}] {1,-10} topo={2} dup={3} MISMATCH ({4:F6} vs {5:F6})",
                                                   mem ? "mem" : "cpu", Configs.Name(mask), topo, dup, v, baseVal);
                    }
        }
        Console.WriteLine(ok ? $"ALL EQUIVALENT (topo): {checked_} config x topology x dup combinations preserve behaviour (cpu+mem)."
                             : "!! TOPOLOGY EQUIVALENCE FAILED");
        return ok ? 0 : 1;
    }

'''

EDITS = [
    ("// ============================ RAPL reader (per-interval delta, package + dram) ============================",
     CLASS + "// ============================ RAPL reader (per-interval delta, package + dram) ============================"),
    ('        if ((args.Length == 5 || args.Length == 6) && args[0] == "matrixk") {',
     VERBS + '        if ((args.Length == 5 || args.Length == 6) && args[0] == "matrixk") {'),
    ("    static string Format(Res r) => string.Format(ci,",
     METHODS + "    static string Format(Res r) => string.Format(ci,"),
]

for i, (old, new) in enumerate(EDITS, 1):
    if src.count(old) != 1:
        sys.exit("!! edit %d: anchor found %d times, expected 1. Program.cs differs from the "
                 "expected version -- STOP and send me your Program.cs." % (i, src.count(old)))
    src = src.replace(old, new)

p.write_bytes(src.encode("utf-8"))
print("Program.cs patched for phase B: ComposedTopo, runktopo, equivtopo added (existing verbs untouched).")
print("Next:  dotnet build -c Release && ./bin/Release/net8.0/proto equivtopo")
