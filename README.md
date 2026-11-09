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
