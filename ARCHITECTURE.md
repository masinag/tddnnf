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

`CompilationContext` is the public entry point for compilation. It owns the
PySMT environment and a `NormalizerWalker`, normalizes the input formula at
construction time, and builds the projection vocabulary.

```python
context = CompilationContext(phi, project_on=atoms)
target = context.compile_treduced(D4Compiler, lemmas)
```

When `project_on` is omitted, the projection consists of the atoms in the
normalized input formula. When supplied, every projection atom is normalized,
a top-level negation is removed so the vocabulary contains positive atoms, and
duplicates are removed while preserving their first occurrence.

Both `compile_treduced()` and `compile_textended()` then:

- normalize every theory lemma in the same environment as the input formula;
- create a fresh `Abstractor`;
- construct the requested compiler with that abstractor;
- pass the normalized formula, lemmas, abstractor, and projection vocabulary to
  the corresponding builder; and
- return a `TheoryCompiledTarget` containing the backend artifact, abstraction,
  and exact projection atoms.

The compiler receives PySMT formulas directly. Atom abstraction happens inside
each backend adapter, allowing all backends to share the same builder API.

## Normalization and projection

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

- `CompilationContext` normalizes the input formula, projection atoms, and
  lemmas before compilation.
- `QueryContext` normalizes query literals, clauses, and cubes before handing
  them to a backend query engine.

Here, the _compiled formula_ is the Boolean abstraction of the
strategy-specific combination of the normalized input formula and normalized
theory lemmas: their conjunction for T-reduced compilation, or the input
formula disjoined with the negated lemmas for T-extended compilation.
Valid projection vocabularies contain only atoms occurring in the normalized
input formula or in the supplied theory lemmas. The ordered
`projection_atoms` list stored in `TheoryCompiledTarget` is the authoritative
query vocabulary. Atoms from the input formula or lemmas that are not requested
are existentially quantified away, and backend query engines reject query atoms
outside this list.

Query-only theory atoms need not occur in the input formula, but they must occur
in the supplied lemmas. Include such atoms in `compilation.project_on` and pass
the complete projection vocabulary to the external lemma enumerator as
`atoms=compilation.project_on`. For T-reduced compilation, enumerate over
`compilation.phi`; for T-extended compilation, enumerate over
`Not(compilation.phi)`. This ensures that every query-only theory atom can occur
in the generated lemmas before those lemmas are supplied to compilation.

## Abstraction and compiled containers

`Abstractor` maintains a bidirectional mapping between SMT atoms and positive
integer IDs. `get_id()` assigns IDs consecutively on first use, while
`get_atom()` performs the reverse lookup. `var_count` reports the number of
mapped atoms and `max_var` reports the largest assigned ID.

The mapping can be serialized with `to_dict()`. Each atom is encoded as a
standalone SMT-LIB script and associated with its integer ID. `from_dict()`
parses those scripts in a supplied PySMT environment, or the global environment
when none is supplied.

`TheoryCompiledTarget[T_Target]` binds three values that must travel together:

- `target`: the backend-specific compiled DAG;
- `abstr`: its SMT-atom-to-integer mapping; and
- `projection_atoms`: the ordered, externally visible vocabulary.

Its `to_pysmt()` method delegates DAG reconstruction to the backend target while
supplying the stored abstraction and a `FormulaManager`.

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
It creates a balanced vtree by default, enables automatic garbage collection
and minimization, and existentially quantifies non-projection variables after
translation.

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

Each backend has a matching query engine: `D4Engine`, `SddEngine`, and
`BddEngine`. All implement the `QueryEngine` protocol:

- `is_satisfiable(assumptions=None)` checks satisfiability, optionally under a
  list of literals;
- `count_truth_assignments(assumptions=None)` counts total assignments over the
  projection vocabulary;
- `is_valid()` checks whether every projected assignment satisfies the target;
- `entails_clause(query_clause)` checks clausal entailment;
- `is_implicant(query_cube)` checks whether a cube implies the target; and
- `enumerate_truth_assignments()` yields total dictionaries from projection
  atoms to Boolean values.

Engines account for forgotten variables when counting and fill missing or
unused projected variables during enumeration. Contradictory assumptions yield
no models.

Backend engines operate on the target's exact atom objects. To make public
queries robust to equivalent SMT syntax, construct a `QueryContext` from the
compiled container and call `wrap_queries(engine)`. The resulting
`NormalizingQueryEngine` aligns assumptions, clauses, and cubes before
delegation.

`QueryContext` indexes every projection atom by its positive canonical form and
tracks polarity separately. It rejects ambiguous projection vocabularies whose
distinct atoms normalize to the same form. Query atoms absent from the index
raise `ValueError`; matching atoms are replaced with the exact objects stored in
the target, with polarity preserved.

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
- `PropCompiler[T]` requires construction with an `Abstractor` and a
  `compile(formula, project_on=None)` method; and
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
├── context.py                  # CompilationContext and QueryContext
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
    ├── normalizing.py         # NormalizingQueryEngine adapter
    ├── d4_engine.py           # d-DNNF queries through ddnnife
    ├── sdd_engine.py          # SDD queries
    └── bdd_engine.py          # OBDD queries
```
