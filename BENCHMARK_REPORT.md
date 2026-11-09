# Benchmark report — final candidate

The official 100-program × 5-machine matrix was run against the final
candidate on 2026-11-09 using `tests/benchmark.py --random 100`.

| Measure | Result |
|---|---:|
| Program/machine combinations | 500 |
| Equivalence/timing passes | 500 |
| Failures or timeouts | 0 |
| Performance regressions | 0 |
| Original total cycles | 580,799 |
| Optimized total cycles | 163,533 |
| Total cycle reduction | 71.84% |
| Geometric-mean speedup | 2.526× |
| Full-matrix wall time | 897.4 seconds |

The matrix used the final MAC cost-model fix. The skewed-machine regression
retains the loop MAC and measures 67 cycles; the buggy revision decomposed the
same loop to 163 cycles. `sum_sq` remains 21 cycles on the public machine and
passes official randomized equivalence validation.

## Largest absolute cycle reductions

| Machine | Program | Before | After | Saved |
|---|---|---:|---:|---:|
| machine_few_registers.cfg | collatz | 15245 | 1229 | 14016 |
| machine_few_registers.cfg | matmul4 | 14121 | 3595 | 10526 |
| machine_few_registers.cfg | nested_invariant | 11614 | 1146 | 10468 |
| machine_few_registers.cfg | sieve | 12906 | 2642 | 10264 |
| machine_few_registers.cfg | strength_ladder | 10240 | 487 | 9753 |
| machine_few_registers.cfg | transpose8 | 10282 | 718 | 9564 |
| machine_no_fused.cfg | matmul4 | 8650 | 1290 | 7360 |
| machine_default.cfg | matmul4 | 8196 | 1018 | 7178 |
| machine_slow_memory.cfg | collatz | 8035 | 1229 | 6806 |
| machine_slow_memory.cfg | matmul4 | 8335 | 1530 | 6805 |

## Additional checks

- 12/12 focused semantic and machine-cost regressions passed.
- 30,000 independent definitions optimized in 0.813 seconds.
- The 100,000-instruction and 1,000-live-register stress cases passed their
  respective execution limits.
- Repeated optimizer invocation produced byte-identical output.

## Reproduction

```sh
./build.sh
python3 tests/regressions.py --kit KIT
python3 tests/stress.py --machine KIT/machines/machine_default.cfg
python3 tests/benchmark.py --kit KIT --out benchmark-full --random 100
```
