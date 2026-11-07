# The Energy of Design-Pattern Compositions — replication package

Replication package for *The Energy of Design-Pattern Compositions: A Controlled Study of
Super-Additive Energy Interactions at Shared Polymorphic Call Sites in .NET 8*.

It contains the benchmark suite, the raw per-run measurements of every campaign reported in the
paper, the hardware-counter and disassembly records on which the mechanism is established, and
the analysis scripts that regenerate every number, table and figure of the manuscript.

**Verified:** running `./reproduce.sh` on this package regenerates `rev5/numbers.tex` — the 1138
macros quoted throughout the paper — and the seven LaTeX tables, byte-identical to the versions
in the submitted manuscript.

## Contents

| Path | What it holds |
|---|---|
| `code/` | The benchmark. `Program.cs` is the current reference kernel, `Program_septembre.cs.txt` the previous one compared in Section 5.5. `patch_dup.py` and `patch_phaseB.py` derive the duplication and topology variants from the same source. |
| `scripts/` | One shell script per campaign, plus `phaseB_common.sh` and the run books. Each script pins the frequency governor, disables Turbo Boost, builds, verifies checksum equivalence, and writes a CSV. |
| `data_campaigns/` | Raw per-run measurements, hardware counters, JIT and kernel disassemblies, machine descriptions. Every column is defined in [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md). |
| `analyse_*.py`, `make_rev5_tex.py` | The analysis chain, at the root because the scripts expect `data_campaigns/` and `rev5/` beside them. |
| `rev5/` | Intermediate results (`values*.json`, `sig.json`, `topology.json`) and final outputs: `numbers.tex`, the seven `tab_*.tex` and the three figures. |
| `reproduce.sh` | Runs the whole chain. |

Measurement environment, versions and machine descriptions: [`ENVIRONMENT.md`](ENVIRONMENT.md).

## Reproducing the numbers of the paper

This needs only Python and the data already in the package — no benchmark run, no special
hardware:

```bash
python3 -m pip install -r requirements.txt
./reproduce.sh
```

The chain has three stages:

1. `analyse_rev5_main.py` reads `data_campaigns/` and writes `rev5/values.json`, `rev5/sig.json`
   and `rev5/topology.json` — relative footprints, interaction deltas, bootstrap standard errors
   and the dual significance criterion. About a minute.
2. `analyse_rev6.py`, `analyse_rev6_pool.py` and `analyse_rev7.py` add the cross-campaign pooling
   (REML with the modified Hartung–Knapp interval), the sensitivity analyses and the energy
   decomposition. These run a non-parametric bootstrap with *B* = 20000 and take roughly fifteen
   minutes. Their outputs are shipped, so `SKIP_SLOW=1 ./reproduce.sh` skips them and uses
   `rev5/values_rev6.json` and `rev5/values_rev7.json` as they are.
3. `make_rev5_tex.py` writes `rev5/numbers.tex`, the seven tables and the figures.

## Re-running the measurements

This needs the hardware and the operating-system configuration described in `ENVIRONMENT.md`,
plus root access for the RAPL counters and for `perf`. Each campaign is one script:

```bash
cd scripts
sudo ./run_dispatch.sh          # dispatch-site experiment, Section 4.5, Table 4
sudo ./run_B4_topology.sh       # invocation topology, Section 4.5, Table 5
sudo ./run_baseline_sweep.sh    # baseline weight sweep, Section 5.2
sudo ./run_B3_tiered.sh         # JIT configuration, Section 5.4
sudo ./run_code_ab.sh           # the two kernel-code versions, Section 5.5
sudo ./run_kernel_diag.sh       # kernel disassemblies, Section 5.5
```

`RUNBOOK_PHASE2.md` and `README_PHASE_B.md` in `scripts/` give the order in which the campaigns
were run.

Absolute energies will differ from ours: they depend on the processor, on its operating point and
on the ambient temperature. What should reproduce is the **structure** of the results — the
retired-instruction surplus at a shared polymorphic call site, its disappearance with dedicated
call sites, and the sign and order of magnitude of the interaction deltas.

## What this package establishes, and what it does not

Hardware counters and disassemblies are the load-bearing evidence, and they reproduce exactly:
the retired-instruction surplus of a composition is identical across machines, workload regimes
and kernel-code versions, to within 0.1 instructions per iteration.

Energy figures do not reproduce exactly, and the paper says so. Whole campaigns run with
identical code differ by more than their within-campaign intervals for some compositions, by up
to 16 points for `BuMe` (Section 6.2). `data_campaigns/` therefore ships every campaign
separately rather than one merged table, so that between-campaign variability can be inspected.

The compiled binaries were not retained.
`data_campaigns/M2b_results_20261020/M2b_code_ab_meta.txt` records the SHA-256 hash of both
measured kernel **sources**, the SDK and Linux kernel versions, the frequency governor and the
turbo setting; according to `M2b_run_all_M2b.log` the same build served the code comparison and
the second topology campaign on Machine 2. The disassemblies in `data_campaigns/kdiag_20261020/`
and `data_campaigns/phaseB/B2/B2_out/` are the record of the machine code actually executed.

Host names and user paths have been replaced by `machine1` and `machine2` throughout, including
inside the `perf` recordings, so that the package can be read without identifying the authors.

## Licences

Code — `code/`, `scripts/`, `analyse_*.py`, `make_rev5_tex.py`, `analyze.py`: **MIT**, see
[`LICENSE`](LICENSE).

Data and documentation — `data_campaigns/`, `rev5/` and the Markdown files: **CC-BY 4.0**, see
[`LICENSE-DATA`](LICENSE-DATA).

## Citing

Please cite the paper. Machine-readable metadata: [`CITATION.cff`](CITATION.cff).

## Contact

Questions and problems: please open an issue on the repository.
