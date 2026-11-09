# Kiln Optimizer

`kopt` is a dependency-free Python 3 optimizer for the Oxygen Debt KIR challenge.

```sh
./build.sh
./kopt input.kir --machine machine.cfg [--profile profile.prof] -o output.kir
```

No installation is required. The optional profile is accepted for command-line compatibility; this correctness-first implementation does not rely on it.

## Test with the official kit

The starter kit is deliberately not included in this repository. Given an unpacked kit directory, validate one result with:

```sh
./kopt KIT/bench/sum_sq.kir --machine KIT/machines/machine_default.cfg -o /tmp/sum_sq.kir
KIT/kvalidate /tmp/sum_sq.kir --against KIT/bench/sum_sq.kir --machine KIT/machines/machine_default.cfg
```

Run the complete 100-program × 5-machine matrix (including official randomized equivalence checks) with:

```sh
python3 tests/benchmark.py --kit KIT --out benchmark-full --random 100
```

The script writes a CSV containing every combination and a Markdown summary. It exits nonzero if any optimizer, validator, simulator, or timeout case fails.

The final candidate was run through the complete matrix on 2026-11-09:
500/500 combinations passed equivalence and timing checks, with zero failures
or regressions. The measured total was 580,799 original cycles versus 163,533
optimized cycles (71.84% reduction), with a 2.526× geometric-mean speedup.
The run took 897.4 seconds wall time. See `BENCHMARK_REPORT.md` for the
largest improvements.

It enforces the contest's five-second optimizer limit for ordinary benchmark
programs. For large-scale limits, run:

```sh
python3 tests/stress.py --machine KIT/machines/machine_default.cfg
```

This checks both a 100,000-instruction program against the 30-second limit and
a 1,000-simultaneously-live-register program against the five-second limit.

## Regression checks

Run the focused semantic, target-cost, and large-block checks with the official kit:

```sh
python3 tests/regressions.py --kit KIT
python3 tests/adversarial.py --kit KIT
python3 tests/stress.py --machine KIT/machines/machine_default.cfg
```

The regression script includes non-SSA loop-definition cases, entry-live initial register values, MAC temporary liveness, deliberately slow fused instructions, and a large number of independent definitions. The adversarial suite is an additional, slower check with fixed per-case randomized validation counts.
