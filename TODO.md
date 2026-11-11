# Deferred work

These items are outside steps 0–7 in [REFACTOR.md](REFACTOR.md). Schedule each
separately after the lean core is integrated. [DESIGN.md](DESIGN.md) records the
ownership and semantic constraints they must preserve.

## Target transformations

Add direct target operations in a separate change: `condition`,
`condition_and_conjoin`, `simplify`, `negate`, `forget`, `conjoin`, and `disjoin`.
Choose supported operations per native representation without introducing a
generic capability framework or automatic recompilation.

Keep propositional semantics explicit: these operations act on the compiled
function, do not enumerate new theory lemmas, and need not preserve a particular
T-reduced/T-extended construction. Preserve semantic immutability and each
operation's vocabulary behavior. Settle contradictory-evidence semantics before
implementation. Keep d-DNNF `simplify()` explicit, idempotent, and separate from
conditioning; test semantic preservation and deterministic output.

## Relational queries and binary native operations

Add `queries.entails(other)` and `queries.is_equivalent(other)` where supported.
Require compatible representations/structures, identical ordered active
vocabularies, and initially the same PySMT environment. Align native IDs by atom
correspondence internally, including imports across compatible managers. Check
SDD vtrees and OBDD orders after alignment. Add focused compatibility and
immutability tests; defer any cross-environment extension separately.

## Native variable allocation

Allocate native variables only for atoms needed by the compiled formula or its
projection, preserving the shared abstraction IDs. Use dense per-target IDs for
SDDs with a persisted abstraction-to-native mapping; for OBDDs, declare only the
needed variable names. Carry the correspondence through compilation, forgetting,
queries, reconstruction, and persistence, preserving native ordering settings.

This removes sparse-ID overhead: with `Abstractor({1: a, 1000: b})`, compiling `a`
with projection `[a]` should allocate one SDD variable rather than 1,000. Current
enumeration constrains all inactive manager variables before yielding a model.
Add sparse-ID and shared-abstraction-growth coverage, including codec round trips
and empty projections. Many variables used in the formula and later forgotten
remain a separate enumeration performance concern.

## Additional reasoners

Evaluate an independent d-DNNF reasoner such as `DecDnnfRsReasoner` against the
persisted NNF codec, all six unary queries, and projection bookkeeping. Document
its native precision and enumeration behavior. Users select the instance
explicitly; it does not silently replace another reasoner. Add a dependency only
with its implemented adapter, retaining the default-installation policy.

## d4 Python compilation

Replace the CLI only when the Python binding supports **projected circuit
compilation**, including elimination of non-projection atoms and encoding
auxiliaries. Confirm the API and installed version with a focused prototype
before scheduling the replacement.

Then preserve configured options, abstraction/NNF remapping, constants, absent
projection atoms, cleanup, error handling, and computation logging. Validate the
same compilation contracts and compare the fixed benchmarks against the CLI.
Do not weaken projection semantics or make the core refactor depend on this
binding becoming available.
