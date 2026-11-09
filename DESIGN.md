# Design

## What is implemented.

The optimizer implements local constant/copy propagation, modular constant folding, safe algebraic identities, local common-subexpression elimination, conservative redundant-load forwarding, constant-branch simplification, unreachable-block deletion, global dead-code elimination, copy coalescing, interference-graph register compaction, fused `mac`/`addsh` formation, canonical-loop invariant code motion, induction-variable div/mod strength reduction, selected constant-multiply strength reduction, and a proven bounded square-sum closed form. It does not unroll loops, perform global alias analysis, or use profile-guided decisions.

## Pass order.

It first propagates simple facts within each block; performs local CSE/load forwarding and machine-aware constant strength reduction; removes unreachable and dead code; coalesces copies; fuses instructions; then performs restricted loop transformations. A final simplify/CSE/dead-code round exposes cleanup created by the loop passes. Interference-graph compaction is last, because it needs the final live ranges.

## Each pass.

Local propagation, CSE, load forwarding, strength reduction, fusion, and copy coalescing are linear per block. CSE entries are invalidated at every source-register redefinition; a load is forwarded only from an identical earlier load with no intervening data store. Reachability is O(V+E). Liveness and dead-code elimination are O(n) per fixed-point iteration. Interference edges are built by the standard definition-versus-live rule (plus one parameter clique), O(sum of live-set sizes); greedy colouring is O(V+E) after graph construction. LICM only accepts a unique-preheader, single-body backedge loop and only hoists pure values not used outside the loop. Its MAC rewrite additionally requires a distinct temporary occurring exactly once and an independent step operand. Div/mod reduction is restricted to a zero-initialized, increment-by-one, signed-checked induction variable, where it remains non-negative. The closed form accepts only a pure canonical square-sum loop whose final bound fact is explicitly proved at most 63, with distinct accumulator, induction, and bound registers; every intermediate product is then exact and the divisor nonzero. Fusions are adjacent and single-use. All transformations are deterministic.

## The machine.

The configuration is read every run. `mac` and `addsh` are emitted only when their corresponding fused feature is enabled. Constant multiplication is changed to a shift/addsh only when the configured replacement latency is no worse than multiplication; div/mod induction reduction only happens when ALU latency is no worse than division latency. Other transformations are target-independent.

## Keeping the behaviour.

`store`, `vload`, `vstore`, `trap`, and potentially trapping operations are never deleted or moved. `load` is retained unless an earlier identical load has already succeeded with no data store between them, which proves both the value and the absence of an address trap. Div/mod are folded only with a known nonzero constant divisor. LICM moves only pure arithmetic and only where the zero-trip outcome cannot observe the destination. No transformation reorders volatile operations or visible stores.

## Profiles.

The optional profile is accepted but deliberately not trusted. Transformations preserve behaviour for every input even if a profile is stale or adversarial.

## Known problems.

The optimizer does not do global alias analysis, global load forwarding, branch-layout/profile tuning, scheduling, generalized induction recognition, loop unrolling, or full SSA construction. LICM intentionally excludes multi-entry and multi-block loops. The greedy allocator reduces name count but is not an optimal graph colourer. These omissions leave performance on complex control flow and memory-heavy programs on the table in exchange for conservative correctness and a bounded running time.
