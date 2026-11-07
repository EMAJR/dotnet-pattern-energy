# Data dictionary

Every file in `data/` is a comma-separated table with a header row. Columns reuse the same
names across campaigns; this file defines them once and then lists which campaign uses which.

## Column definitions

### Identification

| Column | Meaning |
|---|---|
| `rep`, `pass` | Index of the independent execution run (repetition) within the campaign. Runs are executed in randomized order. |
| `config` | Configuration measured. `base` is the pattern-free reference kernel; otherwise a concatenation of two-letter pattern codes (see *Pattern codes* below). |
| `order`, `mask` | Internal bookkeeping of the harness: position of the configuration in the randomized sequence, and the bit mask of active patterns. |
| `regime` | Workload regime: `cpu` for the compute-bound workload ($W_\text{CPU}$), `mem` for the scattered memory-access workload ($W_\text{MEM}$). |
| `version` | Reference-kernel source version: `new` is the current kernel code (`code/Program.cs`), `old` the previous one (`code/Program_septembre.cs.txt`). |
| `topo` | Invocation topology: `shared` (one interface call site for all layers), `dedicated` (one monomorphic site per layer), `direct` (direct call on a field of the sealed concrete type). |
| `dup` | Number of independent instances of the *same* concrete layer. `dup=1` is the normal case; `dup=2,3` is the duplication experiment of Section 4.5. |
| `binary` | JIT configuration: the measured one (tiered compilation disabled) or the .NET 8 default (tiered compilation and dynamic PGO enabled). |
| `weight` | Baseline weight $w$: the number of times the kernel repeats its inner arithmetic step. $w=1$ is the nominal baseline. |
| `K`, `kernel_rep` | Number of sequential tasks in the measurement window, and the repeat count of the kernel inner step. |
| `warmup` | Number of warm-up tasks executed before the measured window (100 in every campaign). |

### Energy and time

| Column | Unit | Meaning |
|---|---|---|
| `e_base` | joule | Intel RAPL package (PKG) energy of the **baseline** run of the pair, over the whole $K$-task window. |
| `e_cfg` | joule | RAPL package energy of the **configuration** run of the same pair. |
| `t_base`, `t_cfg` | second | Wall-clock duration of the same two runs. |
| `energy_J`, `time_s`, `power_W` | J, s, W | Energy, duration and mean power of a single run, when the campaign does not pair. |
| `j_dyn_per_op` | joule | Energy per inner iteration after subtraction of an assumed idle power. Reported for completeness; the paper uses total paired energy without idle subtraction. |

Every run is paired: the harness measures the baseline and the configuration back to back inside
the same process launch, so `e_base` and `e_cfg` on one row share their thermal and frequency
conditions. The relative footprint is `e_cfg / e_base`.

### Hardware counters

| Column | Meaning |
|---|---|
| `cycles` | Retired CPU cycles, read by Linux `perf` around the whole measured window. |
| `instructions` | Retired instructions. This is the quantity on which the mechanism of Section 4.5 is established. |
| `l1d_misses` | L1 data-cache load misses. |
| `dtlb_misses` | Data TLB load misses. |
| `branches`, `branch_misses` | Retired branches and branch mispredictions. |
| `page_faults` | Page faults over the window. |

Counter campaigns run the **same binaries** as the energy campaigns, in separate runs, because
`perf` perturbs the energy measurement.

### Memory and garbage collection

| Column | Unit | Meaning |
|---|---|---|
| `alloc_per_iter`, `alloc_cfg` | byte | Managed-heap allocation per inner iteration, read from the runtime. |
| `gen0`, `gen1`, `gen2` | count | Garbage collections per generation over the window. No promotion beyond generation 0 is observed in any configuration. |
| `gc_pause_ms` | millisecond | Total collector pause time over the window, from `GC.GetTotalPauseDuration()`. |

### Validation

| Column | Meaning |
|---|---|
| `checksum` | Numeric checksum accumulated by the run. Baseline and configuration must agree to within $10^{-6}$; a mismatch invalidates the run. |
| `jit_base`, `jit_cfg` | Number of methods compiled *inside* the measured window. Expected to be 0; one run in 192 in the default JIT configuration is not. |

## Pattern codes

| Code | Pattern | Family |
|---|---|---|
| `St` | Strategy | pure indirection |
| `De` | Decorator | pure indirection |
| `Ad` | Adapter | pure indirection |
| `Fa` | Factory | heap-allocating |
| `Bu` | Builder | heap-allocating |
| `Ob` | Observer | heap-allocating |
| `Me` | Memento | heap-allocating |

Codes concatenate in that order: `FaBuMe` is Factory + Builder + Memento, `StDeAd` is the
pure-indirection control.

## Files by campaign

| File | Campaign | Section of the paper |
|---|---|---|
| `M1_cpu.csv`, `M1_mem.csv`, `M2_cpu.csv`, `M2_mem.csv` | Composition matrices, 26 compositions × 15 runs | 4.1, Table 2 |
| `M1_cpu_ET.csv`, `M1_mem_ET.csv` | Same matrices with time capture, used for the idle-power sensitivity | 5.3, Table 9 |
| `M1_perf_cpu.csv` | Hardware counters, 13 key configurations | 4.5 |
| `M1_alloc_cpu.csv`, `M1_alloc_mem.csv` | Allocation volume and collection counts | 4.5 |
| `M1_gcpause_cpu.csv`, `M1_gcpause_mem.csv` | Collector pause time, $K=2000$ | 4.5, Table 8 |
| `M1_sweep_cpu.csv`, `M1_sweep_cpu_v2.csv` | Baseline weight sweep, $w \in \{1,2,4,8,16,32\}$ | 5.2 |
| `M1_dispatch_energy*.csv`, `M1_dispatch_perf*.csv` | Dispatch-site experiment, two independent campaigns | 4.5, Table 4 |
| `M1_amp_cpu_*.csv`, `M1_amp_mem_*.csv` | Load amplification, $n = 2\times10^5$ and $10^6$ | 4.2 |
| `M1_code_ab.csv`, `M1_code_ab_20261020.csv` | Comparison of the two kernel-code versions | 5.5, Table 6 |
| `M2_cpu_SEP06_unlocked.csv`, `M2_mem_SEP06_unlocked.csv` | Machine-2 campaign before the frequency governor was locked | 5.1 |
| `phaseB/B1_perf_weights.csv` | Counters across baseline weights | 5.2 |
| `phaseB/B2/`, `phaseB/B2b_out.tgz` | JIT disassembly and stub attribution by `perf` sampling | 4.5 |
| `phaseB/B3_energy.csv`, `phaseB/B3_perf.csv` | JIT configuration: measured versus default | 5.4 |
| `phaseB/B4_energy*.csv`, `phaseB/B4_perf.csv` | Topology manipulation on Machine 1 | 4.5, Table 5 |
| `M2_results_20261019/` | Machine-2 replication: idle, weights, topology | 5.1, 4.5 |
| `M2b_results_20261020/` | Machine-2 second topology campaign and code comparison, same build | 4.5, 5.5 |
| `kdiag_20261020/` | Kernel diagnosis: disassemblies and counters of both kernel versions, both machines | 5.5 |
| `M1_machine_info.txt`, `M2_machine_info.txt` | Hardware, kernel and SDK of each machine | 3.5 |

## Disassemblies

| Path | Content |
|---|---|
| `kdiag_20261020/kdiag_M1/asm_{old,new}_{cpu,mem}_{base,FaBuMe}.txt` | JIT disassembly of the reference kernel and of `FaBuMe`, for both source versions and both regimes, Machine 1. |
| `kdiag_20261020/kdiag_M2/asm_*.txt` | Same, Machine 2. |
| `kdiag_20261020/kdiag_M*/addr_*.txt` | Code addresses and sizes corresponding to each disassembly. |
| `phaseB/B2/B2_out/disasm_{tiered,default}_{Bu,BuMe,Bux2,ObMe}.txt` | JIT disassembly of the benchmark loop in both JIT configurations. `tiered` is the measured configuration with tiered compilation disabled. |
| `phaseB/B2/B2_out/jitsummary_*.txt` | JIT compilation summaries for the same runs. |
| `phaseB/B2b_out.tgz` | `perf` sampling with the write-xor-execute double mapping disabled, so that dispatch and resolve stubs can be named (`perfmap_stub_names.txt`). |

## Source hashes

`M2b_results_20261020/M2b_code_ab_meta.txt` records the SHA-256 hash of both measured kernel
sources, together with the SDK version, the Linux kernel version, the frequency governor and the
turbo setting. According to `M2b_run_all_M2b.log`, the same build served the code comparison and
the second topology campaign on Machine 2.

The compiled binaries themselves were not retained. The disassemblies above are the record of
the machine code that was actually executed.
