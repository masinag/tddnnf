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
context = TheoryCompilation(phi, project_on=atoms)
target = context.compile_treduced(D4Compiler(), lemmas)
```

When `project_on` is omitted, the projection consists of the atoms in the
normalized input formula. When supplied, every projection atom is normalized,
a top-level negation is removed so the vocabulary contains positive atoms, and
duplicates are removed while preserving their first occurrence.

Both constructions use one private pipeline to normalize lemmas,
combine them with the formula, prepare an abstraction, compile, and log
counts and durations. Supplied abstractions are reused; otherwise a fresh one is
created. New projection atoms receive IDs first; remaining new atoms follow
SMT-LIB serialization order without DAG aliases. Omitted projection sorts the
normalized formula atoms; explicit empty projection remains empty. Requested
atoms absent from the formula and lemmas are registered as unconstrained atoms.

Compilers are configured instances. Their `compile` methods receive the PySMT
formula, prepared abstraction, projection, and logger for each call; native
translators never allocate IDs. The old builders forward to this pipeline while
preserving caller-supplied abstractions. `CompilationContext` remains an alias.
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
- `target.queries(reasoner)` owns a `QueryContext` and normalizes query literals,
  clauses, and cubes before handing them to a backend query engine.

Here, the _compiled formula_ is the Boolean abstraction of the
strategy-specific combination of the normalized input formula and normalized
theory lemmas: their conjunction for T-reduced compilation, or the input
formula disjoined with the negated lemmas for T-extended compilation.
Projection vocabularies may include atoms absent from the normalized input
formula and supplied theory lemmas; these are unconstrained dimensions. The ordered
`projection_atoms` tuple stored in `TheoryCompiledTarget` is the authoritative
query vocabulary. Atoms from the input formula or lemmas that are not requested
are existentially quantified away, and backend query engines reject query atoms
outside this tuple.

Query-only theory atoms need not occur in the input formula. To constrain them
by theory consistency, they must occur in the supplied lemmas. Include such atoms in `compilation.project_on` and pass
the complete projection vocabulary to the external lemma enumerator as
`atoms=compilation.project_on`. For T-reduced compilation, enumerate over
`compilation.phi`; for T-extended compilation, enumerate over
`Not(compilation.phi)`. This ensures that every query-only theory atom can occur
in the generated lemmas before those lemmas are supplied to compilation.

## Abstraction and compiled containers

`Abstractor` maintains a bidirectional mapping between SMT atoms and positive
integer IDs. `get_id()` validates atoms with `is_atom`, returns existing IDs,
and registers new atoms above the current maximum ID, including sparse mappings.
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

Builders combine already-normalized inputs and delegate propositional
compilation. They do not implement backend-specific translation.

### T-reduced

`TReducedBuilder` compiles

$$
\varphi \land \bigwedge_{C \in \mathit{Cl}} C.
$$

Its lemmas $\mathit{Cl}$ rule out theory-inconsistent propositional
assignments satisfying $\varphi$.

### T-extended

`TExtendedBuilder` compiles

$$
\varphi \lor \bigvee_{C \in \mathit{Cl}} \neg C.
$$

Its lemmas $\mathit{Cl}$ rule out theory-consistent propositional assignments
satisfying $\neg\varphi$.

Each builder records the requested projection list in the returned container.
When a builder is used directly without `project_on`, it derives the projection
from every atom in the combined formula and orders those atoms by abstraction
ID.

## Propositional backends

### d-DNNF: d4

`D4Compiler` translates a PySMT Boolean skeleton to BC-S1.2 circuit syntax with
`BCS12Walker`, invokes the bundled d4 executable, and stores the emitted NNF in
`D4CompiledTarget`. Projected abstraction IDs are remapped to d4's dense output
variable range. Constant results are represented directly as `t 1` or `f 1`.

`D4CompiledTarget` exposes the NNF text, projected variable count, and ID
remapping. It uses `ddnnife` for DAG statistics, while its own NNF parser
reconstructs a PySMT formula.

### SDD: PySDD

`SddCompiler` uses `SddWalker` to build an SDD through recursive Boolean apply.
`SddCompiler(vtree_type="balanced", auto_gc_and_minimize=True)` explicitly
constructs the requested native vtree. The Boolean option jointly enables or
disables native automatic garbage collection and minimization; both are enabled
by default. It existentially quantifies non-projection variables after translation.

`SddCompiledTarget` retains the `SddNode` root and `SddManager`. It provides DAG
statistics and reconstructs decision nodes as disjunctions of prime/sub
conjunctions.

### OBDD: CUDD

`BddCompiler` uses `BddWalker` to translate the Boolean skeleton into a CUDD BDD
and existentially quantifies non-projection variables after translation.

`BddCompiledTarget` retains the CUDD `Function` root and `BDD` manager. It
reports reachable-node and edge counts and reconstructs each decision as an
if-then-else expansion over its SMT atom.

## Queries

`target.queries(CuddReasoner())`, `target.queries(SddReasoner())`, and
`target.queries(DdnnifeReasoner())` open independent sessions over their matching
public backend target classes. Strings, classes, and incompatible pairings raise
`TypeError`. Reasoners and `QuerySession` are exported from `tddnnf.queries`.

Sessions expose the six `QueryEngine` operations: `is_satisfiable`,
`count_truth_assignments`, `is_valid`, `entails_clause`, `is_implicant`, and
`enumerate_truth_assignments`. Each session owns a normalizer bound to `target.env`,
a canonical atom index (through `QueryContext`), and its native adapter. The
legacy `BddEngine`, `SddEngine`, `D4Engine`, and `QueryContext.wrap_queries()`
remain available for existing callers.

Validation traverses all input literals before semantic shortcuts, rejects
compound assumptions, malformed clauses/cubes, and inactive or unknown atoms.
Canonical alignment preserves stored atoms and polarity and rejects ambiguous
matches. Constants, deduplication, contradictions, and elementary derivations
are shared by the session. CUDD/PySDD validity and conditioning remain native;
d-DNNF validity and implicants derive from native counts. No alternate counter
or backend is selected. CUDD floating-point precision, PySDD global-count
overflow, and ddnnife buffering/u64 enumeration limits remain visible (see
[REFACTOR.md](REFACTOR.md)).

Adapters account for forgotten native dimensions, fixed assumptions, sparse IDs,
and unconstrained active atoms. Enumeration returns total assignments keyed by
the exact stored atoms in projection order. SDD and d-DNNF adapters deduplicate
native assignments that differ only on forgotten dimensions.

Sessions support `with` and idempotent `close()`, including initialization failure
and exceptions. Closing releases active iterators, the normalizer, and native
adapter resources (including d-DNNF temporary files). Queries and iterator
advancement on a closed session raise `RuntimeError`. Closing a session preserves
the target and other sessions; finalizers are a fallback.

## Persistence and reconstruction

`TheoryCompiledTarget.save(directory)` creates a directory and writes
`abstraction.json`, containing the SMT-LIB abstraction map and the ordered list
of projection atom IDs. It then delegates backend persistence to `target.save()`.

Backend files are:

| Target              | Circuit file    | `metadata.json` contents                       |
| ------------------- | --------------- | ---------------------------------------------- |
| `D4CompiledTarget`  | `circuit.nnf`   | variable count and abstraction-to-d4 remapping |
| `SddCompiledTarget` | `circuit.sdd`   | PySDD manager variable count                   |
| `BddCompiledTarget` | `circuit.dddmp` | CUDD manager variable count                    |

`TheoryCompiledTarget.load(directory, target_type, env=None)` reverses this
process: it reconstructs the `Abstractor`, asks `target_type.load()` to restore
the backend artifact, resolves projection IDs back to SMT atoms, and returns the
complete container. Supplying the intended PySMT environment keeps restored
atoms in the same formula manager as the caller.

## Protocols and instrumentation

`core/interfaces.py` defines structural protocols rather than a shared backend
base class:

- `PropCompiledTarget` requires `dag_size()`, `save()`, `load()`, and
  `to_pysmt()`;
- `PropCompiler[T]` requires a
  `compile(formula, abstractor, *, project_on=None, computation_logger=None)` method; and
- `QueryEngine[T]` defines the six query operations listed above.

`DagSize` is the common immutable result for target size metrics, reporting
reachable vertices and child-reference edges.

Builders and compilers can receive a shared `dict[str, object]` as
`computation_logger`. `StatsCollector` makes logging optional, accumulates
wall-clock durations, and records counts such as lemmas, atoms, and projection
variables. d4 additionally reports time spent registering atoms, writing the
input circuit, and running the external compiler.

## Package layout

```text
tddnnf/
├── context.py                  # TheoryCompilation and QueryContext
├── core/
│   ├── abstraction.py         # Abstractor mapping and serialization
│   ├── containers.py          # TheoryCompiledTarget
│   ├── interfaces.py          # Backend and query protocols, DagSize
│   ├── pysmt_utils.py         # Atom, clause, cube, and assumption helpers
│   └── stats_collector.py     # Optional timing and count instrumentation
├── normalization/
│   └── normalizer.py          # MathSAT-backed NormalizerWalker
├── builders/
│   ├── reduced.py             # TReducedBuilder
│   └── extended.py            # TExtendedBuilder
├── compilers/
│   ├── d4.py                  # d4/d-DNNF compiler and target
│   ├── pysdd.py               # PySDD compiler and target
│   └── cudd.py                # CUDD OBDD compiler and target
└── queries/
    ├── session.py             # Configured reasoners, validation, lifecycle
    ├── normalizing.py         # NormalizingQueryEngine adapter
    ├── d4_engine.py           # d-DNNF queries through ddnnife
    ├── sdd_engine.py          # SDD queries
    └── bdd_engine.py          # OBDD queries
```
