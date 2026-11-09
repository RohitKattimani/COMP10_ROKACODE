# Benchmark report

This report was produced with the supplied official simulator and validator on
all 100 practice programs and all five supplied machine configurations. Every
matrix case used `kvalidate --against` with its default 100 randomized inputs
plus the sample input.

| Measure | Result |
|---|---:|
| Program/machine combinations | 500 |
| Equivalence/timing passes | 500 |
| Failures or timeouts | 0 |
| Original total cycles | 580,799 |
| Optimized total cycles | 163,112 |
| Total cycle reduction | 71.92% |
| Geometric-mean speedup | 2.531x |
| Full-matrix wall time | 1,104.8 seconds |

The repaired revision enforced a five-second optimizer timeout per normal
program; the slowest optimizer invocation was 1.25 seconds.

The matrix used the repaired, stable optimizer revision, with a five-second
optimizer timeout enforced separately for every normal program. The
bounded-square-sum
closed-form output was additionally validated on all five machines with 1,001
inputs each.

## `sum_sq` final comparison

| Machine | Original | Supplied reference (public machine) | Final optimizer |
|---|---:|---:|---:|
| `machine_default.cfg` | 2690 | 207 | 21 |
| `machine_few_registers.cfg` | 4544 | — | 21 |
| `machine_no_fused.cfg` | 2690 | — | 29 |
| `machine_slow_memory.cfg` | 2696 | — | 25 |
| `machine_wide_fast.cfg` | 690 | — | 19 |

All five final outputs passed official equivalence validation on 1,001 inputs.
The public-machine result is 9.86× faster than the supplied 207-cycle loop
reference and 128.1× faster than the original sample run.

## Largest base-matrix improvements

| Machine | Program | Before | After | Saved |
|---|---|---:|---:|---:|
| `machine_few_registers.cfg` | `collatz` | 15245 | 1229 | 14016 |
| `machine_few_registers.cfg` | `matmul4` | 14121 | 3595 | 10526 |
| `machine_few_registers.cfg` | `nested_invariant` | 11614 | 1146 | 10468 |
| `machine_few_registers.cfg` | `sieve` | 12906 | 2642 | 10264 |
| `machine_few_registers.cfg` | `strength_ladder` | 10240 | 487 | 9753 |
| `machine_default.cfg` | `matmul4` | 8196 | 1018 | 7178 |

There were no performance regressions in the complete 500-row base matrix.

## Runtime check

The supplied 100,000-instruction stress program optimized in 7.703 seconds,
within the 30-second large-program limit.
