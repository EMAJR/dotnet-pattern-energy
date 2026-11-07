# Measurement environment

Both machines run bare-metal Ubuntu 24.04 LTS. No virtualization, no container.

## Machines

| | Machine 1 | Machine 2 |
|---|---|---|
| Processor | Intel Core i7-5600U (Broadwell) | 11th Gen Intel Core i5-1145G7 (Tiger Lake) |
| Logical cores | 4 | 8 |
| Nominal base frequency | 2.60 GHz | 2.60 GHz |
| Measured frequency, Turbo Boost disabled | 2.49 GHz | 1.5 GHz |
| Last-level cache | 4 MB | 8 MB |
| Memory | 8 GB | 16 GB |
| Idle package power | 0.17 W | 1.82 W |
| Transparent huge pages | `madvise` | `madvise` |
| Linux kernel | 6.8.0-136 to 6.8.0-147 | 6.8.0-139 to 6.8.0-147 |
| .NET SDK | 8.0.130 | 8.0.131 |

Raw `lscpu`, `uname` and SDK output: `data/M1_machine_info.txt`, `data/M2_machine_info.txt`.
Per-campaign metadata, including the governor and turbo state actually in force, is written by
each run script next to its CSV.

## Operating-system configuration

Every campaign sets, before measuring:

- frequency governor `performance` on every core;
- Turbo Boost disabled (`/sys/devices/system/cpu/intel_pstate/no_turbo` = 1);
- the benchmark pinned to one logical core.

Simultaneous multithreading remains enabled, and the SMT sibling of the pinned core is **not**
isolated. This is a known limitation, stated in Section 6.2 of the paper.

## Energy measurement

Intel RAPL through the `powercap` interface, package (`PKG`) domain only. The DRAM sub-domain is
present on Machine 1 but is not read by the harness, so memory-access results describe package
energy only.

RAPL is read immediately before and immediately after the whole $K$-task window, outside the
measured loop. The harness performs no allocation and no I/O inside the window.

Energy is reported as **total paired energy, without idle-power subtraction**. The idle power of
each machine was measured directly ($3 \times 60$ s with the same frequency locking) and the
sensitivity of every classification to idle-power subtraction is reported in Section 5.3.

## Runtime configuration

- Release build.
- Workstation, non-concurrent garbage collector.
- Tiered compilation disabled (`DOTNET_TieredCompilation=0`), which also disables dynamic
  profile-guided optimization. This is the measured configuration throughout the paper; the
  default configuration is tested separately in Section 5.4.
- 100 warm-up tasks per process before the measured window.
- Forced full collection between back-to-back runs.
- Runs executed in randomized order: 15 repetitions per configuration in the composition
  matrices, 6 to 20 in the other energy campaigns, 3 to 8 in the counter campaigns.

## Hardware counters

Linux `perf`, around the whole measured window, on the same binaries as the energy campaigns but
in separate runs, because `perf` perturbs the energy measurement. Counter runs use $K = 5000$
tasks so that the benchmark loop accounts for about 98 % of process activity.

For the stub attribution of Section 4.5, the JIT write-xor-execute double mapping was disabled so
that dispatch and resolve stubs could be named in the runtime's perf map. That run changes code
layout and is used for attribution only, never for an energy figure.

## Software versions used by the analysis

The analysis scripts need Python 3.10 or later with the packages listed in `requirements.txt`.
They read only the CSV files in `data/` and are independent of the measurement hardware.
