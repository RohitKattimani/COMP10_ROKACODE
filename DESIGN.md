# Design

## What is implemented.

`kopt` is a deterministic, dependency-free optimizer for KIR. It implements:

- block-local constant and copy propagation, 32-bit modular constant folding, and safe algebraic identities;
- block-local common-subexpression elimination and conservative repeated-load forwarding;
- constant-multiply strength reduction, selected by the target latencies;
- constant-branch simplification and unreachable-block removal;
- global liveness-based dead pure-code elimination;
- adjacent producer/copy coalescing and global virtual-register-name compaction;
- adjacent `mul`/`add` to `mac` and `shl`/`add` to `addsh` fusion when the machine supports the instruction and its latency is not worse than the unfused dependency chain;
- conservative loop-invariant code motion for a single-preheader, single-body loop;
- a structurally proven closed form for a bounded square-sum loop;
- power-of-two division/remainder strength reduction for a proven non-negative counting induction variable.

The optimizer does not build SSA, perform general alias analysis, schedule instructions, insert manual spills, unroll arbitrary loops, or use profile-guided transformations. It intentionally prefers a missed optimization to an unproven rewrite.

## Pass order.

1. Parse the function and machine file.
2. Run block-local propagation/folding, local CSE and load forwarding, and target-aware constant multiplication reduction.
3. Simplify the CFG, remove unreachable blocks and dead pure instructions, then coalesce adjacent copies.
4. Form profitable adjacent fused instructions, coalesce again, and remove newly dead pure instructions.
5. Try the narrowly recognized bounded square-sum closed form, remove unreachable blocks, then run conservative loop-invariant code motion and counting-induction-variable strength reduction.
6. Repeat local propagation/CSE and CFG cleanup to expose simplifications created by loop passes.
7. Run liveness-based register-name compaction and emit the output.

Register compaction is last so its interference graph reflects the final transformed program. The optional profile is accepted by the command line but is not read or trusted.

## Each pass.

Let `n` be the number of instructions, `B` the number of blocks, `R` the number of virtual-register names, and `E` the number of CFG edges.

- **Parsing and emission:** `O(n)` time and `O(n)` storage.
- **Local propagation/folding:** `O(n)` expected time per block over the full scan. Reverse alias links invalidate only aliases of a redefined register; facts never cross a block boundary. Arithmetic folds use explicit 32-bit wraparound semantics. Division and remainder are folded only when the divisor is a known nonzero constant.
- **Local CSE/load forwarding:** `O(n)` expected time and `O(n)` cache storage per block. Reverse indexes invalidate only expressions that depend on a redefined operand or whose result is overwritten. Repeated loads are forwarded only from an identical earlier load with no intervening data store; a volatile operation is never cached.
- **Constant strength reduction:** `O(n)`. Replacing multiplication by a power of two with a shift is exact in 32-bit modular arithmetic. The `addsh` identity is exact for constants of the form `1 + 2^k`.
- **CFG simplification/reachability:** `O(B + E)` for the graph walk and jump-hop simplification.
- **Liveness:** each fixed-point round is `O(n + E)`; the number of rounds depends on the CFG propagation depth. The analysis uses standard `use`/`def` equations.
- **Dead-code elimination:** `O(n)` after liveness. Only pure definitions are removed; potentially trapping operations, stores, and volatile operations remain.
- **Copy coalescing and adjacent fusion:** `O(n)` per pass after liveness. A temporary is eliminated only when its final use is the immediately following copy/consumer and it is not live out of the block. Fusion additionally checks target support and dependency-chain latency.
- **Loop transformations:** the recognizers are deliberately restricted to a single preheader, one body block, one backedge, and a branch header. A LICM destination must have exactly one definition in the loop, must not be used in the header or before that definition, and must not be used outside the loop. Its operands must already be invariant. The special MAC rewrite also checks all uses of the temporary across the whole function. These checks avoid treating non-SSA multiple assignments as one value.
- **Closed-form square sum:** `O(n + B + E)` to inspect the candidate. It requires a zero initial accumulator and induction variable, an explicitly proven bound no larger than 63, distinct bound/accumulator/induction registers, the exact canonical loop body, and an exit that returns the accumulator. This bound keeps all formula intermediates exact and makes the constant divisor nonzero.
- **Induction-variable strength reduction:** linear scan of the recognized loop body. It requires a zero-initialized induction variable with exactly one `+1` update in the loop and a positive power-of-two literal divisor. The signed comparison and bounded run establish non-negativity on terminating executions within the KIR step limit.
- **Register compaction:** interference construction is proportional to the sum of live-set sizes at definitions; greedy colouring is `O(R + I)` after the graph is built, where `I` is the interference-edge count. Parameters interfere with one another, and every parameter interferes with a non-parameter register whose initial zero value is live at function entry. To avoid an unbounded dense graph on pathological high-pressure programs, compaction is skipped when the estimated edge-construction work exceeds 1.5 million. Skipping this optional pass does not change program behaviour.

All pass ordering, iteration order, and register-colouring tie breaks are deterministic.

## The machine.

Every run reads the machine file supplied on the command line. Constant multiplication is changed only when the replacement latency is no greater than `lat_mul`. `mac` fusion is used only when `fused_mac = 1` and `lat_mac <= lat_mul + lat_alu`. `addsh` fusion is used only when `fused_addsh = 1` and `lat_addsh <= 2 * lat_alu`. Induction-variable division/remainder strength reduction is used only when `lat_alu <= lat_div`. The optimizer does not emit either fused instruction when its feature flag is zero. Register compaction reduces the number of distinct virtual names; KIR's simulator applies the machine's hardware-register and spill model to the resulting names.

## Keeping the behaviour.

KIR is not SSA: a register may be assigned multiple times, and source operands are read before the destination is written. The optimizer therefore uses explicit block-local alias invalidation and liveness rather than assuming single assignment. Entry-live non-parameter registers keep their initial zero value distinct from live parameter values during register compaction.

`store`, `vstore`, `vload`, `trap`, and potentially trapping `div`/`mod`/`load`/`store` operations are not removed or moved by dead-code elimination or CSE. Load forwarding requires an earlier identical successful load and no intervening data store. Volatile instructions are never deleted, duplicated, or reordered. Division/remainder folding requires a nonzero constant divisor. LICM moves only pure operations and only when the destination has one loop definition, no loop-header or use-before-definition reads, and no uses outside the loop. The square-sum replacement is guarded by the structural and range proof described above.

The official validator is used in the regression and benchmark scripts; it is the authority for checking returned values, traps, volatile logs, and observable data memory.

## Profiles.

`--profile` is accepted for command-line compatibility, but profiles are deliberately ignored. A missing, incomplete, or incorrect profile therefore cannot change output bytes or cause an unsafe transformation. This gives up profile-driven layout and branch optimizations in exchange for deterministic, input-independent correctness.

## Known problems.

- CSE and load forwarding are local to one basic block; there is no global value numbering or general memory-alias analysis.
- LICM and induction-variable recognition accept only narrow canonical loops. More complex loops are left unchanged.
- The register allocator is a greedy graph colourer, not an optimal allocator. It may skip compaction when estimated graph construction would be too expensive, and KIR's simulator still decides which values spill.
- The optimizer does not schedule instructions or use profile information to improve branch layout, cache behaviour, or hot/cold paths.
- Some individually profitable transformations can still be neutral or unprofitable for particular input distributions; the target-latency guards cover fused operations and scalar strength reductions, not a complete global cycle-cost search.
- Passing a finite validator/benchmark sample is evidence, not a proof of equivalence on every possible KIR input. The competition's hidden cases remain the final test.
