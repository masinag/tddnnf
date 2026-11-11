# Deferred work

These items are outside steps 0–6 in [REFACTOR.md](REFACTOR.md). Schedule each
separately after the lean core is integrated. [DESIGN.md](DESIGN.md) records the
ownership and semantic constraints they must preserve.

## Explicit d-DNNF conversion

`target.to_ddnnf()` returns the same object for an existing d-DNNF target. For
SDD and OBDD targets it converts the native DAG to NNF without compiling a
reconstructed PySMT formula or invoking d4.

Traverse with memoization so shared subgraphs stay shared. OBDD decisions use
their Shannon expansion; SDD decisions use the disjunction of prime/sub pairs.
Preserve constants, literal signs, complemented roots and edges, decomposability,
and determinism. Memoization must distinguish polarity where the native API
uses complemented references. Conversion operates on the reachable DAG without
enumerating satisfying assignments or expanding it into a tree.

The result is another `TheoryCompiledTarget` with an owned NNF representation.
Preserve its abstraction correspondence, owning environment, and exact ordered
active vocabulary, including atoms absent from the DAG. Record any new NNF
remapping and a codec that the d-DNNF reasoner and persistence layer understand.
The result must remain usable independently of source-session lifetimes. This
conversion is explicit; query selection never converts a target implicitly.

An NNF codec identifies its text dialect; d4 output and converted DAGs must not
be confused.

### Acceptance checks

Add `to_ddnnf()` using native DAG traversal and memoization. Existing d-DNNF
targets return themselves. Exercise constants, shared subgraphs, complemented
roots/edges, both literal polarities, and nontrivial native ID mappings. Verify
the conversion preserves abstraction, environment, ordered active vocabulary,
and source semantics without invoking a compiler or enumerating models.

Query converted SDD/OBDD targets through the d-DNNF reasoner using all six unary
operations on small fixtures. Round-trip converted NNF with its declared codec.
Check sharing structurally, not only by comparing truth tables. Separate
conversion errors from the reasoner's already documented native limitations.

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
