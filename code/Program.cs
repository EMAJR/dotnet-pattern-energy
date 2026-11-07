// =====================================================================================
// Phase-2 bench: energy of DESIGN-PATTERN COMPOSITIONS (.NET 8, C#).
//
// Construct validity: all configurations compute the SAME numeric checksum. The functional
// result comes ONLY from chain.Compute(i); every pattern layer adds its characteristic
// structural overhead (dispatch, indirection, heap allocation, GC pressure) WITHOUT changing
// the accumulated value. Any measured energy difference is attributable to structure.
//
// MEASUREMENT PROTOCOL (v2, work-fixed):
//   We run a FIXED number of tasks K (identical work for every config) and measure BOTH
//   energy (RAPL) and wall-clock time. This yields, per config:
//       power_W        = energy_J / time_s
//       dynamic energy = energy_J - idle_W * time_s        (idle floor removed properly)
//       j_dyn_per_op   = dynamic energy / K                (clean per-task dynamic energy)
//   This replaces the earlier fixed-TIME window, under which total energy was power-capped
//   (~constant) and per-task energy collapsed onto run time.
//
// Build : dotnet build -c Release
// Usage :
//   proto equiv                                      -> assert 34 configs == baseline (cpu & mem)
//   proto list                                       -> print the 34 configurations
//   proto idle <seconds>                             -> measure idle package power (W)
//   proto runk <config> <cpu|mem> <n> <K> <idle_W>   -> one work-fixed run (RAPL + time + GC)
//   proto matrixk <cpu|mem> <n> <K> <idle_W>         -> all 34 configs, work-fixed, CSV to stdout
//   proto run <config> <cpu|mem> <n> <s>             -> [legacy] time-fixed run
//   proto matrix <cpu|mem> <n> <s>                   -> [legacy] time-fixed matrix
// =====================================================================================

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;

// ============================ Pattern identifiers ============================
static class Pat {
    public const int Strategy = 0, Decorator = 1, Adapter = 2,
                     Factory = 3, Builder = 4, Observer = 5, Memento = 6;
    public const int N = 7;
    public static readonly string[] Code = { "St", "De", "Ad", "Fa", "Bu", "Ob", "Me" };
}

// ============================ Compute chain (checksum-bearing) ============================
interface ICompute { double Compute(int i); }

// BASELINE WEIGHT (rep): number of times the arithmetic step is repeated per iteration.
// rep = 1 reproduces the original minimal kernel exactly; larger values make the baseline
// progressively heavier, which is how we sweep the denominator of every ratio rho.
// Patterns are untouched: their per-iteration work is identical at every weight.
sealed class KernelCpu : ICompute {
    readonly int rep;
    public KernelCpu(int rep = 1) { this.rep = rep < 1 ? 1 : rep; }
    public double Compute(int i) {
        double v = Math.Sqrt(i * 1.0000001 + 1.0) * 1.0000001;
        for (int r = 1; r < rep; r++) v = Math.Sqrt(v * 1.0000001 + 1.0) * 1.0000001;
        return v;
    }
}
sealed class KernelMem : ICompute {
    readonly double[] buf; readonly int mask; readonly int rep;
    public KernelMem(double[] b, int rep = 1) { buf = b; mask = b.Length - 1; this.rep = rep < 1 ? 1 : rep; } // length must be power of two
    public double Compute(int i) {
        int k = (i * 977) & mask;
        double v = Math.Sqrt(i * 1.0000001 + 1.0) * 1.0000001;
        for (int r = 1; r < rep; r++) v = Math.Sqrt(v * 1.0000001 + 1.0) * 1.0000001;
        buf[k] = v; return buf[k];
    }
}

interface IStep { double Apply(int i); }
sealed class ForwardStep : IStep { readonly ICompute inner; public ForwardStep(ICompute c) { inner = c; } public double Apply(int i) => inner.Compute(i); }
sealed class StrategyLayer : ICompute {
    readonly IStep step; public StrategyLayer(ICompute inner) { step = new ForwardStep(inner); }
    public double Compute(int i) => step.Apply(i);
}
sealed class DecoratorLayer : ICompute {
    readonly ICompute inner; public DecoratorLayer(ICompute c) { inner = c; }
    public double Compute(int i) => inner.Compute(i);
}
interface IIntCompute { long ComputeBits(int i); }
sealed class IntAdaptee : IIntCompute { readonly ICompute inner; public IntAdaptee(ICompute c) { inner = c; } public long ComputeBits(int i) => BitConverter.DoubleToInt64Bits(inner.Compute(i)); }
sealed class AdapterLayer : ICompute {
    readonly IIntCompute a; public AdapterLayer(ICompute inner) { a = new IntAdaptee(inner); }
    public double Compute(int i) => BitConverter.Int64BitsToDouble(a.ComputeBits(i));
}

// ============================ Side pattern layers (overhead only) ============================
interface ISide { void BlockStart(int block); void Step(int i, double v); void BlockEnd(int block); }

sealed class FactoryLayer : ISide {
    sealed class Product { public int Id; public double Seed; }
    Product cur;
    public void BlockStart(int b) { cur = new Product { Id = b, Seed = b }; }
    public void Step(int i, double v) { }
    public void BlockEnd(int b) { }
}
sealed class BuilderLayer : ISide {
    sealed class Builder { readonly List<double> parts = new List<double>(); public Builder Add(double x) { parts.Add(x); return this; } public double Build() { double s = 0; for (int k = 0; k < parts.Count; k++) s += parts[k]; return s; } }
    Builder b; double sink;
    public void BlockStart(int blk) { b = new Builder(); }
    public void Step(int i, double v) { b.Add(v); }
    public void BlockEnd(int blk) { sink += b.Build(); b = null; }
}
sealed class ObserverLayer : ISide {
    // Realistic granularity: notify observers ONCE PER BLOCK (not per step) with one event
    // object. Per-step scalar events are unrealistic and swamp everything in allocation.
    interface IObs { void On(double v); }
    sealed class SumObs : IObs { public double S; public void On(double v) { S += v; } }
    sealed class Evt { public double Value; }
    readonly IObs[] obs; double agg;
    public ObserverLayer() { obs = new IObs[] { new SumObs(), new SumObs(), new SumObs() }; }
    public void BlockStart(int b) { agg = 0; }
    public void Step(int i, double v) { agg += v; }
    public void BlockEnd(int b) { var e = new Evt { Value = agg }; for (int k = 0; k < obs.Length; k++) obs[k].On(e.Value); }
}
sealed class MementoLayer : ISide {
    sealed class Memento { public double[] State; }
    readonly Memento[] ring = new Memento[8]; int idx; readonly int snapLen; double last;
    public MementoLayer(int snapLen) { this.snapLen = snapLen; }
    public void BlockStart(int b) { }
    public void Step(int i, double v) { last = v; }
    public void BlockEnd(int b) { var m = new Memento { State = new double[snapLen] }; for (int k = 0; k < snapLen; k++) m.State[k] = last + k; ring[idx] = m; idx = (idx + 1) & 7; }
}

// ============================ Composed configuration ============================
sealed class Composed {
    readonly ICompute chain; readonly ISide[] sides; readonly int block;
    // dup > 1 instantiates each selected side layer several times, as independent instances
    // of the SAME concrete type. This separates two factors that the mask alone confounds:
    // the number of independent allocating sources (dup increases it) and the polymorphism
    // of the shared dispatch site sides[s].Step (dup leaves it monomorphic, a heterogeneous
    // composition does not). dup = 1 reproduces the original behaviour exactly.
    public Composed(int mask, bool mem, double[] buf, int block, int snapLen, int rep = 1, int dup = 1) {
        this.block = block;
        ICompute k = mem ? (ICompute)new KernelMem(buf, rep) : new KernelCpu(rep);
        if (Has(mask, Pat.Adapter)) k = new AdapterLayer(k);
        if (Has(mask, Pat.Decorator)) k = new DecoratorLayer(k);
        if (Has(mask, Pat.Strategy)) k = new StrategyLayer(k);
        chain = k;
        var s = new List<ISide>();
        for (int d = 0; d < (dup < 1 ? 1 : dup); d++) {
            if (Has(mask, Pat.Factory)) s.Add(new FactoryLayer());
            if (Has(mask, Pat.Builder)) s.Add(new BuilderLayer());
            if (Has(mask, Pat.Observer)) s.Add(new ObserverLayer());
            if (Has(mask, Pat.Memento)) s.Add(new MementoLayer(snapLen));
        }
        sides = s.ToArray();
    }
    static bool Has(int mask, int p) => (mask & (1 << p)) != 0;
    public double Run(int n) {
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
}

// ============================ Configuration enumeration ============================
static class Configs {
    public static List<int> All() {
        var list = new List<int> { 0 };
        for (int p = 0; p < Pat.N; p++) list.Add(1 << p);
        for (int i = 0; i < Pat.N; i++)
            for (int j = i + 1; j < Pat.N; j++) list.Add((1 << i) | (1 << j));
        int[][] tri = {
            new[]{ Pat.Observer, Pat.Memento, Pat.Builder },
            new[]{ Pat.Strategy, Pat.Decorator, Pat.Adapter },
            new[]{ Pat.Strategy, Pat.Observer, Pat.Memento },
            new[]{ Pat.Factory,  Pat.Builder,  Pat.Memento },
            new[]{ Pat.Adapter,  Pat.Observer, Pat.Memento },
        };
        foreach (var t in tri) { int m = 0; foreach (var p in t) m |= (1 << p); list.Add(m); }
        return list;
    }
    public static string Name(int mask) {
        if (mask == 0) return "base";
        var sb = new StringBuilder();
        for (int p = 0; p < Pat.N; p++) if ((mask & (1 << p)) != 0) sb.Append(Pat.Code[p]);
        return sb.ToString();
    }
    public static int Order(int mask) { int c = 0; for (int p = 0; p < Pat.N; p++) if ((mask & (1 << p)) != 0) c++; return c; }
    public static int FromName(string name) {
        if (name == "base") return 0;
        if (int.TryParse(name, out int m)) return m;
        int mask = 0;
        for (int p = 0; p < Pat.N; p++) if (name.Contains(Pat.Code[p])) mask |= (1 << p);
        return mask;
    }
}

// ============================ RAPL reader (per-interval delta, package + dram) ============================
sealed class Rapl {
    readonly List<string> paths = new List<string>(); readonly List<long> last = new List<long>(); readonly List<long> max = new List<long>();
    public bool Available => paths.Count > 0;
    public Rapl() {
        const string root = "/sys/class/powercap/intel-rapl";
        if (!Directory.Exists(root)) return;
        foreach (var d in Directory.GetDirectories(root)) {
            string np = Path.Combine(d, "name"), ep = Path.Combine(d, "energy_uj");
            if (!File.Exists(ep) || !File.Exists(np)) continue;
            string nm = File.ReadAllText(np).Trim();
            if (!(nm.StartsWith("package") || nm == "dram")) continue;
            try {
                long raw = long.Parse(File.ReadAllText(ep).Trim());
                long mx = 0; string mp = Path.Combine(d, "max_energy_range_uj");
                if (File.Exists(mp)) mx = long.Parse(File.ReadAllText(mp).Trim());
                paths.Add(ep); last.Add(raw); max.Add(mx);
            } catch { }
        }
    }
    public double ReadDeltaJoules() {
        double total = 0;
        for (int i = 0; i < paths.Count; i++) {
            long raw = long.Parse(File.ReadAllText(paths[i]).Trim());
            long d = raw - last[i]; if (d < 0) d = max[i] > 0 ? d + max[i] : 0;
            last[i] = raw; total += d / 1e6;
        }
        return total;
    }
}

// ============================ Main ============================
static class Program {
    const int BLOCK = 1024, SNAP = 16, MEMBUF = 1 << 22; // 32 MB buffer: exceeds any laptop cache -> truly memory-bound
    static readonly CultureInfo ci = CultureInfo.InvariantCulture;

    static int Main(string[] args) {
        if (args.Length >= 1 && args[0] == "equiv") return Equiv(args.Length >= 2 ? int.Parse(args[1], ci) : 1);
        if (args.Length >= 1 && args[0] == "list") { foreach (var m in Configs.All()) Console.WriteLine("{0,-2} {1,-14} order={2} mask={3}", Configs.Order(m), Configs.Name(m), Configs.Order(m), m); return 0; }
        if (args.Length == 2 && args[0] == "idle") {
            double s = double.Parse(args[1], ci);
            var rapl = new Rapl();
            if (!rapl.Available) { Console.Error.WriteLine("RAPL not available (check chmod on /sys/class/powercap/intel-rapl)."); return 3; }
            rapl.ReadDeltaJoules(); var sw = Stopwatch.StartNew(); Thread.Sleep((int)(s * 1000)); sw.Stop();
            double j = rapl.ReadDeltaJoules(); double t = sw.Elapsed.TotalSeconds;
            Console.WriteLine(string.Format(ci, "idle: energy_J={0:F3} time_s={1:F3} idle_power_W={2:F4}", j, t, j / t));
            return 0;
        }
        if ((args.Length == 6 || args.Length == 7) && args[0] == "runk") {
            int mask = Configs.FromName(args[1]); bool mem = args[2] == "mem";
            int n = int.Parse(args[3], ci); long K = long.Parse(args[4], ci); double idleW = double.Parse(args[5], ci);
            int rep = args.Length == 7 ? int.Parse(args[6], ci) : 1;
            Console.WriteLine(Format(MeasureK(mask, mem, n, K, idleW, rep))); return 0;
        }
        if (args.Length == 7 && args[0] == "runkdup") {
            int mask = Configs.FromName(args[1]); bool mem = args[2] == "mem";
            int n = int.Parse(args[3], ci); long K = long.Parse(args[4], ci); double idleW = double.Parse(args[5], ci);
            int dup = int.Parse(args[6], ci);
            Console.WriteLine(Format(MeasureK(mask, mem, n, K, idleW, 1, dup)) + string.Format(ci, " dup={0}", dup));
            return 0;
        }
        if ((args.Length == 5 || args.Length == 6) && args[0] == "matrixk") {
            bool mem = args[1] == "mem"; int n = int.Parse(args[2], ci); long K = long.Parse(args[3], ci); double idleW = double.Parse(args[4], ci);
            int rep = args.Length == 6 ? int.Parse(args[5], ci) : 1;
            Console.WriteLine("config,order,mask,regime,K,energy_J,time_s,power_W,j_dyn_per_op,alloc_per_iter,gen0,gen1,gen2,checksum,kernel_rep,gc_pause_ms");
            foreach (var mask in Configs.All()) { Console.WriteLine(Csv(MeasureK(mask, mem, n, K, idleW, rep))); Console.Out.Flush(); }
            return 0;
        }
        Console.Error.WriteLine("usage: proto equiv [rep] | list | idle <s> | runk <config> <cpu|mem> <n> <K> <idle_W> [rep] | runkdup <config> <cpu|mem> <n> <K> <idle_W> <dup> | matrixk <cpu|mem> <n> <K> <idle_W> [rep]");
        return 2;
    }

    struct Res { public int mask; public bool mem; public long K; public int rep; public double time, energy, power, jdyn, checksum, pauseMs; public long allocPerIter; public int g0, g1, g2; }

    // Work-fixed measurement: exactly K identical tasks, energy + time + GC, idle-subtracted.
    // rep = baseline weight (see KernelCpu/KernelMem); rep = 1 is the original minimal baseline.
    static Res MeasureK(int mask, bool mem, int n, long K, double idleW, int rep = 1, int dup = 1) {
        double[] buf = mem ? new double[MEMBUF] : null;
        var comp = new Composed(mask, mem, buf, BLOCK, SNAP, rep, dup);
        for (int w = 0; w < 100; w++) comp.Run(n);               // warm-up: JIT + caches + GC steady state (100 needed for alloc-heavy configs)
        GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
        var rapl = new Rapl(); if (rapl.Available) rapl.ReadDeltaJoules();
        long a0 = GC.GetTotalAllocatedBytes(true);
        int g0 = GC.CollectionCount(0), g1 = GC.CollectionCount(1), g2 = GC.CollectionCount(2);
        // Total time the runtime spent in GC pauses. Sampled like the allocation counters,
        // i.e. OUTSIDE the measured loop but bracketing exactly the same K-task window.
        // Available since .NET 7. This separates "how OFTEN the collector runs" (gen0 count,
        // already known to be additive) from "how MUCH WORK each collection does" (pause time).
        TimeSpan p0 = GC.GetTotalPauseDuration();
        var sw = Stopwatch.StartNew(); double sink = 0;
        for (long i = 0; i < K; i++) sink += comp.Run(n);        // exactly K identical tasks
        sw.Stop();
        double energy = rapl.Available ? rapl.ReadDeltaJoules() : double.NaN;
        double t = sw.Elapsed.TotalSeconds;
        double pauseMs = (GC.GetTotalPauseDuration() - p0).TotalMilliseconds;
        long alloc = GC.GetTotalAllocatedBytes(true) - a0;
        double dyn = energy - idleW * t;                          // remove idle floor over actual time
        return new Res {
            mask = mask, mem = mem, K = K, rep = rep, time = t, energy = energy, power = energy / t,
            jdyn = dyn / K, checksum = sink / K, allocPerIter = alloc / Math.Max(1, K), pauseMs = pauseMs,
            g0 = GC.CollectionCount(0) - g0, g1 = GC.CollectionCount(1) - g1, g2 = GC.CollectionCount(2) - g2
        };
    }

    static string Format(Res r) => string.Format(ci,
        "config={0} regime={1} K={2} kernel_rep={3} time_s={4:F3} energy_J={5:F3} power_W={6:F3} j_dyn_per_op={7:E4} alloc_per_iter={8} gen0={9} gen1={10} gen2={11} gc_pause_ms={12:F3} checksum={13:F6}",
        Configs.Name(r.mask), r.mem ? "mem" : "cpu", r.K, r.rep, r.time, r.energy, r.power, r.jdyn, r.allocPerIter, r.g0, r.g1, r.g2, r.pauseMs, r.checksum);

    static string Csv(Res r) => string.Format(ci,
        "{0},{1},{2},{3},{4},{5:F3},{6:F3},{7:F3},{8:E6},{9},{10},{11},{12},{13:F6},{14},{15:F3}",
        Configs.Name(r.mask), Configs.Order(r.mask), r.mask, r.mem ? "mem" : "cpu", r.K,
        r.energy, r.time, r.power, r.jdyn, r.allocPerIter, r.g0, r.g1, r.g2, r.checksum, r.rep, r.pauseMs);

    // Equivalence must be re-verified at every baseline weight: the checksum value changes
    // with rep, but all 34 configurations must still agree with the baseline at that weight.
    static int Equiv(int rep = 1) {
        int n = 100000; bool ok = true; int checked_ = 0;
        foreach (bool mem in new[] { false, true }) {
            double[] buf = mem ? new double[MEMBUF] : null;
            double baseVal = new Composed(0, mem, buf, BLOCK, SNAP, rep).Run(n);
            foreach (var mask in Configs.All()) {
                if (mask == 0) continue;
                double v = new Composed(mask, mem, buf, BLOCK, SNAP, rep).Run(n);
                bool eq = Math.Abs(v - baseVal) < 1e-6; ok &= eq; checked_++;
                if (!eq) Console.WriteLine("[{0}] {1,-14} MISMATCH ({2:F6} vs {3:F6})", mem ? "mem" : "cpu", Configs.Name(mask), v, baseVal);
            }
        }
        Console.WriteLine(ok ? $"ALL EQUIVALENT (rep={rep}): {checked_} configs preserve behaviour (cpu+mem)." : $"!! EQUIVALENCE FAILED (rep={rep})");
        return ok ? 0 : 1;
    }
}
