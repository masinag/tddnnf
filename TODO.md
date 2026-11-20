# Deferred work

## Explicit d-DNNF conversion

`target.to_ddnnf()` returns the same object for an existing d-DNNF target. For
SDD and OBDD targets it converts the native DAG to NNF without compiling a
reconstructed PySMT formula or invoking d4.

Traverse with memoization so shared subgraphs stay shared. OBDD decisions use
their Shannon expansion; SDD decisions use the disjunction of prime/sub pairs.
Preserve constants, literal signs, complemented roots and edges,
decomposability, and determinism. Memoization must distinguish polarity where
the native API uses complemented references. Conversion operates on the
reachable DAG without enumerating satisfying assignments or expanding it into a
tree.

The result is another `TheoryCompiledTarget` with an owned NNF representation.
Preserve its abstraction correspondence, owning environment, and exact ordered
active vocabulary, including atoms absent from the DAG. The result must remain
usable independently of source-session lifetimes. This conversion is explicit;
query selection never converts a target implicitly.

## Target transformations

Add direct target operations in a separate change: `condition`,
`condition_and_conjoin`, `simplify`, `negate`, `forget`, `conjoin`, and
`disjoin`. Choose supported operations per native representation without
introducing a generic capability framework or automatic recompilation.

Keep propositional semantics explicit: these operations act on the compiled
function, do not enumerate new theory lemmas, and need preserve a
T-reduced/T-extended property according to the theoretical foundation paper.
Keep d-DNNF `simplify()` explicit, idempotent, and separate from conditioning;
test semantic preservation and deterministic output.

## Relational queries and binary native operations

Add `queries.entails(other)` and `queries.is_equivalent(other)` where supported.
Require compatible representations/structures, identical ordered active
vocabularies, and initially the same PySMT environment. Possibly, align native
IDs by atom correspondence internally, including imports across compatible
managers. Check SDD vtrees and OBDD orders after alignment. Add focused
compatibility and immutability tests; defer any cross-environment extension
separately.

## Additional reasoners

Evaluate an independent d-DNNF reasoner such as `DecDnnfRsReasoner` against the
persisted NNF codec, all six unary queries, and projection bookkeeping. Document
its native precision and enumeration behavior. Users select the instance
explicitly; it does not silently replace another reasoner. Add a dependency only
with its implemented adapter, retaining the default-installation policy.

## d4 Python compilation

Replace the CLI only when the Python binding supports **projected circuit
compilation**, including elimination of non-projection atoms and encoding
auxiliaries.
