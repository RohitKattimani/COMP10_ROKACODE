# Benchmark report — current source package

The following checks were run against the official Oxygen Debt starter kit.
The kit's `bench/`, `examples/`, and `machines/` directories are not copied
into this package.

## Completed checks

| Check | Result |
|---|---:|
| Official-validator semantic regression cases | 12/12 passed |
| Explicit machine-cost assertions | 3/3 passed |
| Independent-definition scalability case | 30,000 definitions in 1.031 s |
| 100,000-instruction stress program | 4.133 s (30 s limit) |
| 1,000 simultaneously-live-register stress program | 1.339 s (5 s limit) |
| `sum_sq` equivalence on default machine | 101 inputs passed |
| `sum_sq` optimized cycles on default machine | 21 |
| Repeated optimizer invocation | Byte-identical output |
| Fresh Git checkout: `./build.sh` and `./kopt` | Passed |

The semantic regressions cover multiple definitions in loops, loop
use-before-definition, entry-zero values versus parameters, self-updating
arithmetic/CSE, self-addressing loads, live and dead MAC temporaries, and
machine-dependent fusion/decomposition. The additional slow-multiply loop test
prevents loop MAC decomposition when `lat_mul + lat_alu > lat_mac`.

The `sum_sq` optimized output contains eight instructions and takes 21 cycles
on `machine_default.cfg`, compared with 2,690 cycles for the supplied original
program. The official validator reported 101 checked inputs for this run.

The skewed-machine regression that exposed the loop-MAC cost-model bug was also
rechecked after the fix: the optimized output retained the MAC and took 67
cycles; the buggy revision had decomposed it and took 163 cycles. Both versions
were semantically equivalent, so this was a performance-only defect.

## Incomplete checks (not counted as passes)

- The extended `tests/adversarial.py` run did not complete within a 300-second
  wall-clock cap. Its partial output is not counted as a pass.
- A multi-machine practice-program benchmark sample did not complete within
  the available wall-clock cap. No full 100-program x 5-machine equivalence or
  cycle claim is made for this package.
- The 500-combination figures in the superseded report belonged to a different
  source revision and are intentionally not claimed here.

## Reproduction

With an unpacked official kit at `KIT`, run:

```sh
./build.sh
python3 tests/regressions.py --kit KIT
python3 tests/stress.py --machine KIT/machines/machine_default.cfg
python3 tests/adversarial.py --kit KIT
python3 tests/benchmark.py --kit KIT --out benchmark-full --random 100
```

The last command runs the full 100-program x 5-machine matrix. Its output is
not included because a complete matrix did not finish in this environment.
