#!/usr/bin/env python3
# =====================================================================================
# Idempotent patch: adds the `dup` parameter and the `runkdup` verb to Program.cs.
#
# `dup` instantiates the SAME concrete side layer several times, as independent
# instances. This separates two factors the pattern mask confounds:
#   - the number of independent allocating sources  (dup increases it)
#   - the polymorphism of the shared dispatch site sides[s].Step(i, v)
#     (dup leaves it MONOMORPHIC; a heterogeneous composition makes it polymorphic)
# dup = 1 reproduces the current behaviour exactly, so every existing campaign,
# script and CSV stays valid.
#
# Usage:  python3 patch_dup.py          (run from the folder containing Program.cs)
# =====================================================================================
import sys, pathlib

p = pathlib.Path("Program.cs")
if not p.exists():
    sys.exit("!! Program.cs not found. Run this from the pattern_energy_bench folder.")
src = p.read_text(encoding="utf-8")

if "runkdup" in src:
    print("Program.cs already patched (runkdup present). Nothing to do.")
    sys.exit(0)

EDITS = [
    # 1. Composed constructor: add the dup parameter
    ("    public Composed(int mask, bool mem, double[] buf, int block, int snapLen, int rep = 1) {",
     "    // dup > 1 instantiates each selected side layer several times, as independent\n"
     "    // instances of the SAME concrete type. dup = 1 reproduces the original behaviour.\n"
     "    public Composed(int mask, bool mem, double[] buf, int block, int snapLen, int rep = 1, int dup = 1) {"),

    # 2. Side-layer construction: wrap in a replication loop
    ("        var s = new List<ISide>();\n"
     "        if (Has(mask, Pat.Factory)) s.Add(new FactoryLayer());\n"
     "        if (Has(mask, Pat.Builder)) s.Add(new BuilderLayer());\n"
     "        if (Has(mask, Pat.Observer)) s.Add(new ObserverLayer());\n"
     "        if (Has(mask, Pat.Memento)) s.Add(new MementoLayer(snapLen));\n"
     "        sides = s.ToArray();",
     "        var s = new List<ISide>();\n"
     "        for (int d = 0; d < (dup < 1 ? 1 : dup); d++) {\n"
     "            if (Has(mask, Pat.Factory)) s.Add(new FactoryLayer());\n"
     "            if (Has(mask, Pat.Builder)) s.Add(new BuilderLayer());\n"
     "            if (Has(mask, Pat.Observer)) s.Add(new ObserverLayer());\n"
     "            if (Has(mask, Pat.Memento)) s.Add(new MementoLayer(snapLen));\n"
     "        }\n"
     "        sides = s.ToArray();"),

    # 3. MeasureK: accept and forward dup
    ("    static Res MeasureK(int mask, bool mem, int n, long K, double idleW, int rep = 1) {\n"
     "        double[] buf = mem ? new double[MEMBUF] : null;\n"
     "        var comp = new Composed(mask, mem, buf, BLOCK, SNAP, rep);",
     "    static Res MeasureK(int mask, bool mem, int n, long K, double idleW, int rep = 1, int dup = 1) {\n"
     "        double[] buf = mem ? new double[MEMBUF] : null;\n"
     "        var comp = new Composed(mask, mem, buf, BLOCK, SNAP, rep, dup);"),

    # 4. New CLI verb, inserted before matrixk
    ('        if ((args.Length == 5 || args.Length == 6) && args[0] == "matrixk") {',
     '        if (args.Length == 7 && args[0] == "runkdup") {\n'
     '            int mask = Configs.FromName(args[1]); bool mem = args[2] == "mem";\n'
     '            int n = int.Parse(args[3], ci); long K = long.Parse(args[4], ci); double idleW = double.Parse(args[5], ci);\n'
     '            int dup = int.Parse(args[6], ci);\n'
     '            Console.WriteLine(Format(MeasureK(mask, mem, n, K, idleW, 1, dup)) + string.Format(ci, " dup={0}", dup));\n'
     '            return 0;\n'
     '        }\n'
     '        if ((args.Length == 5 || args.Length == 6) && args[0] == "matrixk") {'),

    # 5. Usage string
    ('usage: proto equiv [rep] | list | idle <s> | runk <config> <cpu|mem> <n> <K> <idle_W> [rep] | matrixk',
     'usage: proto equiv [rep] | list | idle <s> | runk <config> <cpu|mem> <n> <K> <idle_W> [rep] | runkdup <config> <cpu|mem> <n> <K> <idle_W> <dup> | matrixk'),
]

for i, (old, new) in enumerate(EDITS, 1):
    if src.count(old) != 1:
        sys.exit("!! edit %d: anchor found %d times, expected 1. Program.cs differs from the "
                 "expected version -- STOP and send me your Program.cs." % (i, src.count(old)))
    src = src.replace(old, new)

p.write_bytes(src.encode("utf-8"))
print("Program.cs patched: 5 edits applied.")
print("Next:  dotnet build -c Release  &&  ./bin/Release/net8.0/proto equiv")
