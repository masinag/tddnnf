# Lean core design

**Status: implemented public contracts.** Execution evidence is in
[REFACTOR.md](REFACTOR.md); usage and implementation details are in
[README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Follow-up work is in
[TODO.md](TODO.md).

## Public interface and compilation

The public concepts are `TheoryCompilation`, `TheoryCompiledTarget`, the backend
classes `BddCompiledTarget`, `SddCompiledTarget`, and `D4CompiledTarget`,
configured compiler instances, and query engine classes. The public
workflow is:

```python
with TheoryCompilation(phi, project_on=atoms, env=env) as compilation:
    enumerator.check_all_sat(compilation.phi, atoms=compilation.project_on)
    lemmas = enumerator.get_theory_lemmas()
    target = compilation.compile_treduced(D4Compiler(), lemmas)

with target.queries(DdnnifeEngine) as queries:
    satisfiable = queries.is_satisfiable()
    count = queries.count_truth_assignments()
```

Theory-lemma enumeration remains external. T-reduced compilation uses lemmas
enumerated over normalized `phi`; T-extended compilation uses lemmas enumerated
over `Not(compilation.phi)`, with the same projection vocabulary, then calls
`compile_textended(compiler, lemmas)`.

The methods differ only in the formula they construct:

- T-reduced: `phi AND AND(lemmas)`.
- T-extended: `phi OR OR(NOT(lemma) for lemma in lemmas)`.

Both accept keyword-only `abstractor: Abstractor | None = None` after the existing
compiler, lemmas, and optional computation logger positional arguments. Supplied
abstractions retain existing IDs and append new registrations.

Both use one private pipeline for normalization, validation, abstraction,
projection, compilation, target construction, and computation logging.
Compilers receive the PySMT DAG and prepared abstraction. Retain separate
native translators where their APIs differ; a custom Boolean AST or generic
visitor framework is unnecessary.

Pass instances such as `D4Compiler()`, `SddCompiler()`, and `BddCompiler()`.
Backend options belong in their constructors. Passing a string or a compiler
class is an API error. Query sessions instead accept the matching engine class:
`DdnnifeEngine`, `SddEngine`, or `BddEngine`. No reasoner layer is needed.

`D4Compiler` retains the d4 CLI, BC-S1.2 circuit translation, projected
compilation, subprocess error handling, temporary-file cleanup, and computation
logging. Replacing it with a Python binding is deferred until that binding
provides projected circuit compilation. Preserve the effective PySDD and CUDD
translation, projection, minimization, and reordering settings unless a focused
acceptance check exposes an adapter defect.

## Atoms, environment, and stable IDs

`TheoryCompilation(phi, project_on=None, env=None)` selects the supplied PySMT
environment or the active environment when omitted. Stored formula nodes must
belong to that environment. Normalize the formula, supplied projection entries,
and later the lemmas there. Callers must respect type hints and supply Boolean
formulas/lemmas and DAGs entirely from that formula manager, including embedded
nodes. These are caller preconditions; normalization relies on `DagWalker`
memoization without repeated type checks or environment-validation traversals.

Projection entries normalize to positive Boolean symbols or theory atoms;
strip a normalized top-level negation and reject arbitrary Boolean formulas.
Deduplicate after normalization, retaining explicit first-occurrence order.
When projection is omitted, sort normalized formula atoms by `FNode.node_id()`.
An explicit empty projection remains empty.

**Projection atoms may be absent from both the formula and the lemmas.** Register
them anyway: they are unconstrained variables in the represented propositional
function. The caller supplies theory lemmas appropriate to the requested
vocabulary; compilation does not run an additional enumerator.

Reuse a supplied abstraction or allocate a fresh one when absent. Preserve
existing IDs and register new atoms above the current maximum, in this order:

1. All active projection atoms, in their declared order.
2. Remaining atoms of the combined normalized formula, in `FNode.node_id()` order.

Node IDs are sorting keys only; new abstraction IDs remain sequential above the
current maximum. Ordering is reproducible given the same node creation history
in the environment and starting abstraction, independently of set iteration,
hash randomization, and backend traversal. Existentially eliminate every
non-projection atom and encoding auxiliary. Keep abstraction IDs distinct from native variable IDs, NNF IDs,
and OBDD levels; explicit mappings connect them. A backend may renumber or
reorder without changing the public vocabulary. Migrated artifacts retain
their existing IDs instead of applying the new allocation order.

## Target and resource ownership

`TheoryCompiledTarget` binds a public backend compiled target, abstraction,
ordered active vocabulary (`projection_atoms`), and owning PySMT environment.
`BddCompiledTarget`, `SddCompiledTarget`, and `D4CompiledTarget` remain public
classes, available through the supported read-only `.target` property.

Target bindings use read-only properties; the shared abstraction remains
append-only. Its constructor copies input mappings and its public views are read-only, with no
deletion or reassignment API. Compilers and targets receive the same abstractor.
SDD counting uses the native manager's variable count so later registrations,
sparse IDs, and the minimum one-variable constant manager cannot change query
dimensions. BDD and d4 keep their existing native dimensions. Concurrent mutation
is unsupported; saving may include atoms registered by later compilations.

| Owner | Owned state and responsibilities |
| --- | --- |
| Compilation session | Normalized inputs, one pipeline, normalizer and its solver resources |
| TheoryCompiledTarget | Bound environment, stable abstraction, immutable ordered active vocabulary, backend target |
| D4CompiledTarget | NNF text, variable count, abstraction-to-NNF remapping, codec metadata |
| SddCompiledTarget | Root references, manager, abstraction-to-native remapping, final vtree, codec metadata |
| BddCompiledTarget | Root references, manager, final variable order, codec metadata |
| Query session | Independent normalizer, transient atom index, engine resources and temporary files |

Native roots retain their managers for as long as needed. A target survives
closure of the compilation session; closing one query session leaves the target
and other sessions usable. Targets own no normalizers, live solvers, or
normalization configuration. Public backend compiled targets encapsulate native
ownership and codecs.

Immutability is semantic: the represented Boolean function, abstraction
correspondence, environment, and ordered active vocabulary remain unchanged.
Native reordering or minimization is allowed, so node identity, shape, and DAG
size need not stay fixed. Do not expose mutable vocabulary or mapping state
that lets callers violate these invariants.

Compilation and query sessions support `with` and explicit, idempotent
`close()`. Release owned resources on normal exit, exceptions, and partial
initialization failure; reject operations on closed sessions. Enumeration
iterators depend on their open session. Finalizers are only a fallback.

Retain `to_pysmt()` reconstruction into the target's environment, `DagSize`
metrics (reachable vertices and child-reference edges), and computation
logging through the existing `StatsCollector` conventions. Reconstruction
restores the represented propositional function over the stored theory atoms;
it need not recover the original source syntax. Backend metrics describe their
native DAGs and are not promises of identical sizes across representations.

## Query sessions and backend authority

`target.queries(Engine)` validates representation compatibility and returns a
shared session that exposes all six unary queries:

| Operation | Meaning over the active vocabulary |
| --- | --- |
| `is_satisfiable(assumptions=None)` | Some model satisfies the target and assumptions |
| `count_truth_assignments(assumptions=None)` | Count total assignments satisfying the target and assumptions |
| `is_valid()` | Every assignment satisfies the target |
| `entails_clause(clause)` | Every target model satisfies the clause |
| `is_implicant(cube)` | Every assignment satisfying the cube satisfies the target |
| `enumerate_truth_assignments()` | Enumerate satisfying total assignments keyed by exact stored atoms |

The session normalizes the stored vocabulary with its own normalizer and builds
a transient canonical atom index, preserving each stored atom's polarity.
Normalize incoming literals, clauses, and cubes with that same normalizer and
align them to the exact stored atoms before encoding native literals. Reject
ambiguous canonical matches, malformed inputs, and atoms outside the active
scope. An inactive atom is not queryable merely because it has an abstraction
ID. Normalization accepts equivalent syntax when it produces the same canonical
atom; it is not a general SMT equivalence check.

The session accepts clause/cube formulas, flattens them iteratively, and delegates
aligned literal lists to the matching engine methods. Direct engines and custom
`QueryEngine` implementations must accept flat `list[FNode]` clauses/cubes;
formula inputs are no longer supported by engines. Assumption signatures are unchanged.
Engines share constant handling and deduplication for assumptions and cubes, and
validate every list entry before semantic shortcuts. Contradictory assumptions return
`False` for satisfiability and `0` for counting, without asking the backend.
Handle contradiction introduced by normalization as well as explicit `a` and
`Not(a)`. A tautological clause is entailed; a contradictory cube is an
implicant. Empty clause and cube cases follow their usual Boolean semantics.
Assumptions restrict a query; they do not change the target or its vocabulary.

Counting and enumeration include every active atom, even when absent from the
DAG. Projection bookkeeping translates IDs, removes irrelevant native counting
dimensions, accounts for unconstrained active atoms, and expands partial native
models into total assignments in projection order. Fixed assumptions must not
be counted as free dimensions. Keep this bookkeeping distinct from evaluating
the represented function.

The selected backend supplies the answers. Share input handling and elementary
query derivations in the session, but use native primitives for reasoning. Do
not implement a Python model counter, silently substitute another backend, or
repair native numerical limits with a second reasoning implementation.
Precision, overflow, and enumeration buffering limits remain visible and are
documented with the installed versions and reproductions established in step 1.
Derived answers inherit the limitations of the native primitive they use.
Unsupported representation/engine combinations fail explicitly.

## Deferred d-DNNF conversion

Explicit `to_ddnnf()` conversion is outside this refactor. Its specification and
acceptance checks are retained in [TODO.md](TODO.md#explicit-d-dnnf-conversion).

## Persistence and migration

Use `target.save(path)` and `TheoryCompiledTarget.load(path, TargetClass, env=...)`.
Callers explicitly select the compiled-target class; metadata describes the
representation. Keep the existing artifact layout:

- `abstraction.json`: SMT-LIB atom serialization and ordered active IDs.
- `metadata.json`: schema version, representation family, codec, declared
  payload files, and representation metadata.
- `circuit.nnf`, or `circuit.sdd` with `circuit.vtree`, or `circuit.dddmp`.

Record d-DNNF variable counts and remapping, the actual saved SDD vtree, and the
complete OBDD variable-to-level order after reordering. An NNF codec identifies
its text dialect. Metadata describes artifacts, not compiler/engine
configuration or a normalizer.

Parse atoms into the requested environment, or the active environment by
default. Treat package-produced metadata, abstraction IDs, ordered projection,
mappings, and native payloads as trusted state. Keep only the schema-version
gate; codec and file declarations remain descriptive fields, not a validation
contract. Missing data and library errors propagate naturally. Load saved vtrees
and OBDD orders before importing roots. Each backend owns persistence using its native library; shared
helpers handle metadata and filesystem publication only.

Do not recheck compilation invariants or maintain handwritten graph validators or
custom SDD reconstruction. Malformed or manually edited artifacts may load
incorrectly, raise ordinary exceptions, or crash native readers. d4 loading
preserves NNF text without certifying graph correctness. Saves do not reconstruct
abstractions or reload native payloads. Migration calls the public loader in a
subprocess to contain native-reader failures.

Only an explicitly identified legacy SDD artifact that never saved a vtree may
use the balanced-vtree fallback. If migration produces versioned metadata for
one, it must record that legacy exception explicitly instead of declaring a
nonexistent file. Never silently apply the fallback to a damaged current
artifact. An unsaved original vtree cannot be recovered: validate loadability
and report this limitation without claiming recovery of its original shape or
guaranteeing semantics for an unknown incompatible original vtree.

Write complete artifacts through a temporary sibling destination and publish
after serialization completes. Refuse accidental source or destination overwrites;
failure leaves the source and any existing valid destination intact. Clean up
temporary writes deterministically.

The legacy migration command belongs in `tddnnf-testbench`. Support individual
artifacts, recursive discovery, and dry runs. Preserve abstraction IDs,
projection order, logs, and native payload bytes; upgrade metadata without
theory or propositional recompilation. Retain an existing SDD vtree, identify
the legacy missing-vtree case, and recover OBDD order from the DDDMP header.
Check historical recovery data locally and backend loadability in the subprocess;
report failures per artifact. Update library and benchmark consumers through
linked companion PRs in step 5 (or
earlier when an interface change requires it).

## Reserved operation semantics

Transformations and relational queries are follow-up work, not acceptance
requirements for this refactor. Preserve these contracts for that work:

- Operations have propositional semantics over the compiled abstraction. They
  do not enumerate fresh theory lemmas or re-establish a different theory
  compilation construction.
- `condition(mu)` restricts the function and removes assigned atoms from the
  active vocabulary; `condition_and_conjoin(mu)` also retains the evidence and
  the original vocabulary. `forget(atoms)` existentially removes those atoms;
  `negate()` preserves vocabulary.
- Keep `simplify()` explicit and separate from conditioning. Its future d-DNNF
  implementation preserves semantics and vocabulary and is idempotent; do not
  hide it inside another transformation.
- Future `conjoin`, `disjoin`, `entails`, and `is_equivalent` require compatible
  representation structures, identical ordered active vocabularies, and
  initially the same PySMT environment. Match atoms and align native IDs
  internally; equal integer IDs alone do not establish correspondence.
- Different native managers are allowed when a compatible import is possible.
  Validate SDD vtrees and OBDD orders after atom alignment. Incompatibility is
  an error, not permission for implicit recompilation or vocabulary changes.
- Transformations return new targets and preserve operand semantics; unsupported
  native operations fail explicitly. Detailed support and contradictory-evidence
  behavior must be settled in the separate transformation work.

## Scope and verification

Retain existing runtime dependencies, MathSAT normalization, reconstruction,
DAG metrics, and computation logging. Additional reasoners and a d4 Python
binding are deferred. No public registry, generic capability framework, or
new abstraction hierarchy is required.

Use small pytest functions, explicit backend parameterization, useful existing
helpers, and focused native tests. Test tddnnf's normalization, mapping,
ownership, projection, and persistence obligations. Record upstream precision
and buffering limitations separately from adapter defects. Step-by-step
acceptance checks and benchmark comparisons are defined in [REFACTOR.md](REFACTOR.md).
