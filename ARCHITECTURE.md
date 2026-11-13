# Architecture

`tddnnf` exposes compilation and query interfaces for SMT formulas represented
with PySMT. During compilation, it combines the input formula with a suitable
set of theory lemmas, builds a Boolean abstraction of the combined formula, and
passes that abstraction to a propositional backend. The resulting artifact
retains the mapping between propositional variables and SMT atoms.

The supported targets are d-DNNF through d4, SDD through PySDD, and OBDD
through CUDD.

The workflow has two stages:

Compilation:

1. normalize SMT syntax and choose the atoms to retain;
2. combine the input formula with theory lemmas; and
3. map SMT atoms to propositional variables and compile the Boolean abstraction.

Querying:

1. normalize queries against the vocabulary stored with the compiled target;
   and
2. use a backend-specific propositional query engine to answer them.

Here, the vocabulary is the target’s `projection_atoms`: the normalized SMT atoms
selected for projection and available to queries.

## Compilation flow

`TheoryCompilation` is the public entry point for compilation. It owns the
PySMT environment and a `NormalizerWalker`, normalizes the input formula at
construction time, and builds the projection vocabulary.

```python
from tddnnf import TheoryCompilation, TheoryCompiledTarget

with TheoryCompilation(phi, atoms=atoms) as compilation:
    target = compilation.compile_treduced(D4Compiler(), lemmas, abstractor=abstractor)
```

When `atoms` is omitted, the projection consists of the atoms in the
normalized input formula. When supplied, every projection atom is normalized,
a top-level negation is removed so the vocabulary contains positive atoms, and
duplicates are removed while preserving their first occurrence. Entries that
normalize to constants are discarded. Missing normalized input atoms raise
`ValueError`. Atoms are Boolean symbols or theory relations, not underlying
SMT symbols. Formula and lemma inputs must be quantifier-free; the normalizer raises
`UnsupportedOperatorError` for quantified inputs.

Both constructions use one private pipeline to normalize lemmas,
combine them with the formula, prepare an abstraction, compile, and log
counts and durations. Supplied abstractions are reused; otherwise a fresh one is
created. New projection atoms receive IDs first; remaining new atoms follow
normalized atoms’ `FNode.node_id()` order. Omitted projection sorts the
normalized formula atoms by the same key. The declaration must include every
normalized input atom; empty declarations require atom-free input. Requested atoms absent from the formula and lemmas are registered as
unconstrained atoms.
Node IDs only determine sorting; abstraction IDs are allocated sequentially above
the existing maximum. Ordering is reproducible given the same node creation
history in the environment and starting abstraction.

Compilers are configured instances. Their `compile` methods receive the PySMT
formula, prepared abstraction, atom declarations, and logger for each call; native
translators never allocate IDs. Both public compilation methods accept keyword-only
`abstractor=None`; a supplied mapping is reused with append-only registration.
The old `CompilationContext` alias and builders are removed; use `TheoryCompilation`
and its `compile_treduced` or `compile_textended` methods.
Compilation sessions and normalizers support `with` and idempotent `close()`,
including cleanup on exceptions and initialization failure. Closed sessions
reject operations. Query sessions provide the same explicit lifecycle.

## Normalization and projection

Callers must respect the annotated Python types and provide Boolean formulas
from the selected environment, including every descendant. The normalizer
trusts these preconditions and uses `DagWalker` memoization without a separate
validation traversal. SDD configuration types are likewise caller preconditions;
unsupported vtree names still raise `ValueError` before entering native code.

The architecture requires theory atoms to be in some canonical forms.
Compilation and querying must map equivalent theory atoms
to the same PySMT atom; otherwise, equivalent spellings can produce different
propositional variables or fail query-vocabulary lookup. For example,
$x \leq y$ and $x - y \leq 0$ must converge, as must $x \geq 2$ and
$2x \geq 4$.

`NormalizerWalker` currently meets this requirement pragmatically by
round-tripping each theory relation through MathSAT and using the term returned
by MathSAT's converter as its canonical PySMT representation. Boolean
connectives are rebuilt from their normalized children; constants, symbols,
and non-relational theory operators are retained. MathSAT is therefore an
implementation dependency of the current normalizer, not a fundamental
requirement of the architecture: another normalizer could replace it if it
provided the same deterministic, semantics-preserving canonicalization.

Normalization occurs at both boundaries:

- `TheoryCompilation` normalizes the input formula, projection atoms, and
  lemmas before compilation.
- `target.queries(Engine)` owns normalization and normalizes query literals,
  clauses, and cubes before handing them to a backend query engine.

Here, the _compiled formula_ is the Boolean abstraction of the
strategy-specific combination of the normalized input formula and normalized
theory lemmas: their conjunction for T-reduced compilation, or the input
formula disjoined with the negated lemmas for T-extended compilation.
Projection vocabularies may include atoms absent from the normalized input
formula and supplied theory lemmas; these are unconstrained dimensions. The ordered
`projection_atoms` tuple stored in `TheoryCompiledTarget` is the authoritative
query vocabulary. All normalized input atoms must be declared. Generated
lemma atoms are existentially eliminated for reduced compilation and universally
eliminated for extended compilation. Backend query engines reject atoms outside
this tuple.

Query-only theory atoms need not occur in the input formula. To constrain them
by theory consistency, they must occur in the supplied lemmas. Include such atoms in `compilation.atoms` and pass
the complete projection vocabulary to the external lemma enumerator as
`atoms=compilation.atoms`. For T-reduced compilation, enumerate over
`compilation.phi`; for T-extended compilation, enumerate over
`Not(compilation.phi)`. This ensures that every query-only theory atom can occur
in the generated lemmas before those lemmas are supplied to compilation.

## Abstraction and compiled targets

`Abstractor` maintains a bidirectional mapping between SMT atoms and positive
integer IDs. `get_id()` validates atoms with `is_atom`, returns existing IDs,
and registers new atoms above the current maximum ID, including sparse mappings.
Boolean constants raise `ValueError` in constructor mappings, `get_id()`, and
`from_dict()`, which reuses constructor validation. Rejected registrations leave
both mappings and the next available ID unchanged. The shared `is_atom()`
predicate still accepts constants for other formula and query helpers.
`get_atom()` performs the reverse lookup. `var_count` reports the number of
mapped atoms and `max_var` reports the largest assigned ID. Constructor mappings
are copied; `id_to_atom` and `atom_to_id` are read-only views of private dictionaries.
There is no public deletion or reassignment API.

Compilation extends a supplied abstractor in stable order and passes that same
object to the compiler and target. Append-only sharing preserves callers' IDs
and lets later compilations register atoms without invalidating earlier targets.
Targets expose bindings through getter properties and keep projection tuples;
the shared abstractor remains append-only.
SDD counting derives forgotten dimensions from the target's native manager,
not the growing map; BDD and d4 retain their existing native counting dimensions.
Concurrent mutation is unsupported. Saving a target serializes the current map,
which may include atoms registered by later compilations.

The mapping can be serialized with `to_dict()`. Each atom is encoded as a
standalone SMT-LIB script and associated with its integer ID. `from_dict()`
parses those scripts in a supplied PySMT environment, or the global environment
when none is supplied.

`TheoryCompiledTarget[T_Target]` binds four read-only values that must travel together:

- `target`: the backend-specific compiled DAG;
- `abstr`: its SMT-atom-to-integer mapping; and
- `projection_atoms`: the ordered, externally visible tuple; and
- `env`: the owning PySMT environment.

Projection order and membership define the target's query dimensions. Storing
the vocabulary as a tuple prevents later mutation from invalidating query
indexes and counting assumptions, and isolates the target from changes to
constructor input lists.

Its `to_pysmt()` method delegates DAG reconstruction to the backend target while
supplying the stored abstraction and its bound environment’s formula manager.
Public reconstruction is argument-free: `target.to_pysmt()`. `target.dag_size()`
delegates metrics to the backend target. `BddCompiledTarget`, `SddCompiledTarget`,
and `D4CompiledTarget` are public backend classes, exposed through the supported
read-only `.target` property. Native roots and managers stay together, using the
bindings’ reference ownership. d4 remapping is copied and exposed read-only.

## Compilation strategies

Both public methods normalize inputs and delegate to the shared pipeline.

### T-reduced

`compilation.compile_treduced(compiler, lemmas)` compiles

$$
\varphi \land \bigwedge_{C \in \mathit{Cl}} C.
$$

Its lemmas $\mathit{Cl}$ rule out theory-inconsistent propositional
assignments satisfying $\varphi$.

### T-extended

`compilation.compile_textended(compiler, lemmas)` compiles

$$
\varphi \lor \bigvee_{C \in \mathit{Cl}} \neg C.
$$

Its lemmas $\mathit{Cl}$ rule out theory-consistent propositional assignments
satisfying $\neg\varphi$.

Both methods retain the session’s complete ordered `atoms` vocabulary in the
returned container, defaulting to normalized input atoms in node-ID order.
Only lemma atoms outside that vocabulary are eliminated: existentially for
reduced compilation, universally for extended compilation.

## Propositional backends

### d-DNNF: d4

`D4Compiler` translates a PySMT Boolean skeleton to BC-S1.2 circuit syntax with
`BCS12Walker`, invokes the bundled d4 executable, and stores the emitted NNF in
`D4CompiledTarget`. Compilation creates a dense mapping before translation,
assigning retained atoms first and quantified atoms afterward. The walker
and circuit declarations use those native IDs; the target retains the complete
declared mapping, including on constant return paths. Constant results are
represented directly as `t 1` or `f 1`. Universal declarations raise
`NotImplementedError` before invoking d4.

`D4CompiledTarget` exposes the NNF text, projected variable count, and ID
remapping. It uses `ddnnife` for DAG statistics, while its own NNF parser
reconstructs a PySMT formula.

### SDD: PySDD

`SddCompiler` uses `SddWalker` to build an SDD through recursive Boolean apply.
`SddCompiler(vtree_type="balanced", auto_gc_and_minimize=True)` explicitly
constructs the requested native vtree. The Boolean option jointly enables or
disables native automatic garbage collection and minimization; both are enabled
by default. After translation it eliminates declared universal variables using
`not exists U. not F`, or eliminates declared existential variables.

`SddCompiledTarget` retains the `SddNode` root, `SddManager`, and a read-only
abstraction-to-native `remapping`. Compilation allocates dense native IDs in
ascending abstraction-ID order for declared `all_atoms` only. Queries,
forgetting, reconstruction, and persistence use this correspondence. Constants
retain a one-variable manager. Forgotten variables remain in the manager. It provides DAG
statistics and reconstructs decision nodes as disjunctions of prime/sub
conjunctions.

### OBDD: CUDD

`BddCompiler` uses `BddWalker` to translate the Boolean skeleton into a CUDD BDD
and eliminates either declared universal or declared existential variables.

`BddCompiledTarget` retains the CUDD `Function` root and `BDD` manager. It
reports reachable-node and edge counts and reconstructs each decision as an
if-then-else expansion over its SMT atom.

## Queries

`target.queries(BddEngine)`, `target.queries(SddEngine)`, and
`target.queries(DdnnifeEngine)` open independent sessions over their matching
public backend target classes. Strings, engine instances, and incompatible pairings raise
`TypeError`. Engines and `QuerySession` are exported from `tddnnf.queries`.

Sessions expose the six `QueryEngine` operations: `is_satisfiable`,
`count_truth_assignments`, `is_valid`, `entails_clause`, `is_implicant`, and
`enumerate_truth_assignments`. Each session owns a normalizer bound to `target.env`,
a canonical atom index, and its native adapter. Direct engines remain available;
`QueryContext` and its normalizing wrapper have been removed in favor of sessions.

Validation traverses all input literals before semantic shortcuts, rejects
compound assumptions, malformed clauses/cubes, and inactive or unknown atoms.
Canonical alignment preserves stored atoms and polarity and rejects ambiguous
matches. Sessions accept clause/cube formulas and flatten and align literals once.
Engines accept flat `list[FNode]` clauses/cubes and share constant, duplicate, and
complement handling; assumptions use the same conjunction handling as cubes.
Direct callers and custom engines must migrate former formula signatures to lists.
Every engine input is validated before semantic shortcuts. CUDD/PySDD validity
and conditioning remain native;
d-DNNF validity and implicants derive from native counts. No alternate counter
or backend is selected. CUDD floating-point precision, PySDD global-count
overflow, and ddnnife buffering/u64 enumeration limits remain visible (see
[REFACTOR.md](REFACTOR.md)).

Adapters account for forgotten native dimensions, fixed assumptions, sparse IDs,
and unconstrained active atoms. Enumeration returns total assignments keyed by
the exact stored atoms in projection order. The SDD adapter deduplicates native assignments that differ only on forgotten
dimensions. D4 artifacts map retained atoms first, followed by quantified atoms, to dense native
IDs, including atoms absent from the DAG; query engines assert this invariant.

Sessions support `with` and idempotent `close()`, including initialization failure
and exceptions. Each enumeration call creates an independent generator. The session
lazily creates and tracks its engine generator on first iteration, delegates
assignments without copying, and unregisters it when iteration ends or the caller
closes the generator. Unstarted enumerations use no engine resources and stop if
started after session closure. Closing the session stops every active engine
generator before releasing the native adapter (including d-DNNF temporary files)
and normalizer, continuing cleanup even if a close raises. Query methods on a
closed session raise `RuntimeError`; its enumerations raise `StopIteration`.
Closing a session preserves the target and other sessions; finalizers are a fallback.

`QueryEngine.enumerate_truth_assignments()` must return a closable
`Generator[dict[FNode, bool], None, None]`, including for structural engines.
Arbitrary iterators do not satisfy this contract. Engine `close()` must be
idempotent; subclasses of `QueryEngine` inherit a no-op default.

## Persistence and reconstruction

`TheoryCompiledTarget.save(directory)` writes a versioned artifact containing
`abstraction.json` (SMT-LIB atom scripts, original IDs, and ordered
`projection_atom_ids`), `metadata.json`, and the native payload. Standalone backend
`save()` and `load()` use their native libraries and the same metadata format
without the abstraction file. External targets implement `PropCompiledTarget`
without registration; each backend supplies its codec and complete payload file
list to `write_metadata(directory, representation, *, codec, files, **extra)`.
The container depends on the backend protocol; backend implementations use the
metadata/filesystem helpers. `core/persistence.py` owns no native codecs or
graph validators.

| Representation | Codec | Native files | Structural metadata |
| --- | --- | --- | --- |
| OBDD | `dddmp-2.0` | `circuit.dddmp` | complete `variable_order`, `var_count` |
| SDD | `pysdd` | `circuit.sdd`, `circuit.vtree` | actual manager vtree, `var_count`, `remapping` |
| d-DNNF | `d4` | `circuit.nnf` | `var_count`, abstraction-to-native `remapping` |

All metadata declares `schema_version: 1`, `representation` (built-ins use `obdd`,
`sdd`, or `ddnnf`), `codec`, and payload `files`. Saves serialize into a temporary
sibling artifact, refuse existing destinations, and clean up failed writes before
publication.

`TheoryCompiledTarget.load(directory, target_type, env=None)` delegates loading
and metadata schema validation to the supplied backend class, then reconstructs
the abstraction and ordered projection directly in the supplied PySMT environment.
Every backend, including external implementations of `PropCompiledTarget`, must
validate its schema in `load(directory)` for both direct and container loads.
Built-ins use `read_metadata()`; the container does not read metadata on load.
Metadata and payloads are trusted package-owned state; codec and file declarations
are descriptive conventions.
Vtrees are restored and the saved OBDD variable order is declared before native
import, with CUDD automatic reordering disabled. Each backend owns save/load:
CUDD dumps/loads DDDMP, PySDD saves/reads SDD and vtree files, and d4 writes/reads
NNF text directly. Saves do not reconstruct abstractions or reload native payloads.

There are no metadata cross-checks, handwritten native graph validators, or
custom SDD reconstruction. Malformed or manually edited artifacts may load
incorrectly, raise ordinary exceptions, or crash native readers;
d4 loading preserves text without certifying graph correctness. Successful loading
does not certify a circuit's semantics.

Unversioned artifacts require recompilation with the current library; the
standalone testbench migration tool has been removed. Consumers select the backend
explicitly and delegate schema checks to its loader without separate metadata or
representation checks. Every SDD artifact must include `circuit.vtree`; loads
restore it before reading the SDD. Artifacts missing their saved vtree require
recompilation; there is no fallback or provenance flag. Historical compilation
timings remain historical evidence and need fresh timed runs.

## Protocols and instrumentation

`core/interfaces.py` defines structural protocols rather than a shared backend
base class:

- `PropCompiledTarget` requires `dag_size()`, `save()`, `load()`, and
  `to_pysmt()`;
- `PropCompiler[T]` requires a
  `compile(formula, abstractor, *, all_atoms, exists_atoms=(), forall_atoms=(), computation_logger=None)`
  method implementing `exists E. F` or `forall U. F`, rejecting mixed requests. The complete declared vocabulary
  includes absent free dimensions; quantified variables must be disjoint subsets
  and every formula atom must be declared. Invalid declarations raise `ValueError`,
  and the abstraction must be prepared before compilation; and
- `QueryEngine[T]` defines the six query operations listed above.

`DagSize` is the common immutable result for target size metrics, reporting
reachable vertices and child-reference edges.

Compilation methods and compilers can receive a shared `dict[str, object]` as
`computation_logger`. `StatsCollector` makes logging optional, accumulates
wall-clock durations, and records counts such as lemmas, atoms, and projection
variables. d4 additionally reports time spent registering atoms, writing the
input circuit, and running the external compiler.

## Package layout

```text
tddnnf/
├── context.py                  # TheoryCompilation
├── core/
│   ├── abstraction.py         # Abstractor mapping and serialization
│   ├── theory_compiled_target.py          # TheoryCompiledTarget
│   ├── interfaces.py          # Backend and query protocols, DagSize
│   ├── pysmt_utils.py         # Atom, clause, cube, and assumption helpers
│   └── stats_collector.py     # Optional timing and count instrumentation
├── normalization/
│   └── normalizer.py          # MathSAT-backed NormalizerWalker
├── compilers/
│   ├── d4.py                  # d4/d-DNNF compiler and target
│   ├── pysdd.py               # PySDD compiler and target
│   └── cudd.py                # CUDD OBDD compiler and target
└── queries/
    ├── session.py             # Normalization, validation, lifecycle
    ├── ddnnife_engine.py       # d-DNNF queries through ddnnife
    ├── sdd_engine.py          # SDD queries
    └── bdd_engine.py          # OBDD queries
```

Native allocation preserves shared abstraction IDs. OBDD compilation declares
only needed `b<ID>` names in ascending ID order. Both SDD and d4 target
constructors interpret omitted or empty mappings as identity over their native
variable range; nonempty mappings are retained exactly and exposed read-only.
SDD schema v1 artifacts require the `remapping` field; a missing field remains
an error, including in older payloads.
