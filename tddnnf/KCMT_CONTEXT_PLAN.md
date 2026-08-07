# Compilation And Query Contexts Implementation Plan

## High-Level Design

Use two small public context classes with different, always-valid state:

- `CompilationContext` owns normalized compilation inputs.
- `QueryContext` owns alignment against one target's exact `projection_atoms`.

`TheoryCompiledTarget` is the boundary between them:

```text
raw phi + projection atoms
        |
        v
CompilationContext
        |
        v
TheoryCompiledTarget  -- save/load -->  QueryContext
                                            |
                                            v
                                NormalizingQueryEngine
```

This reflects the real workflow. Compilation and querying may happen in the
same process or in separate processes, but both query paths reconstruct their
state from the compiled target.

Existing low-level components remain available:

- Builders construct T-reduced or T-extended formulas.
- Compilers produce d-DNNF, SDD, or BDD artifacts.
- Raw query engines remain backend-specific.
- `TheoryCompiledTarget` continues to persist the backend artifact, abstraction,
  and projection-atom vocabulary.

Only three context-layer classes are needed:

1. `CompilationContext`
2. `QueryContext`
3. `NormalizingQueryEngine`

Do not add an atom-alignment class or vocabulary class. `QueryContext` can keep
one private dictionary:

```python
dict[canonical_atom, tuple[compiled_atom, target_negated]]
```

## Public API

### Same-Process Workflow

```python
from pysmt.shortcuts import And, GT, Not, Or, Plus, Real, Symbol
from pysmt.typing import REAL
from tlemma_enum.solvers.mathsat_total import MathSATTotalEnumerator

from tddnnf import CompilationContext, QueryContext
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.queries.d4_engine import D4Engine

x = Symbol("x", REAL)
y = Symbol("y", REAL)

xgt5 = GT(x, Real(5))
xgt0 = GT(x, Real(0))
ygt5 = GT(y, Real(5))
xpygt5 = GT(Plus(x, y), Real(5))

phi = Or(And(xgt0, ygt5), And(xgt5, xpygt5))
clause = Or(xgt5, xpygt5)
assumptions = [Not(ygt5), Not(xgt0)]

compilation = CompilationContext(phi)

enumerator = MathSATTotalEnumerator()
enumerator.check_all_sat(compilation.phi, atoms=compilation.project_on)
lemmas = enumerator.get_theory_lemmas()

target = compilation.compile_treduced(D4Compiler, lemmas=lemmas)

queries = QueryContext(target)
engine = queries.wrap_queries(D4Engine(target))

print(engine.is_satisfiable(assumptions))
print(engine.entails_clause(clause))
print(engine.count_truth_assignments())
for model in engine.enumerate_truth_assignments():
    print(model)
```

Even in one process, create `QueryContext` from the returned target. This keeps
same-process behavior identical to save/load behavior and avoids making a
compilation context change meaning after compilation.

### Offline Compilation

```python
from pathlib import Path

from pysmt.fnode import FNode
from pysmt.shortcuts import read_smtlib

from tddnnf import CompilationContext
from tddnnf.compilers.d4 import D4Compiler


def split_lemmas(node: FNode) -> list[FNode]:
    return list(node.args()) if node.is_and() else [node]


phi = read_smtlib("formula.smt2")
lemmas = split_lemmas(read_smtlib("lemmas.smt2"))

compilation = CompilationContext(phi)
target = compilation.compile_treduced(D4Compiler, lemmas=lemmas)
target.save(Path("compiled-ddnnf"))
```

Compilation methods defensively normalize external or loaded lemmas.

### Queries In A Later Process

```python
from pathlib import Path

from pysmt.shortcuts import read_smtlib

from tddnnf import QueryContext
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.d4_engine import D4Engine

target = TheoryCompiledTarget.load(Path("compiled-ddnnf"), D4CompiledTarget, env=env)
queries = QueryContext(target, env=env)
engine = queries.wrap_queries(D4Engine(target))

query = read_smtlib("query.smt2")
print(engine.is_implicant(query))
```

The explicit raw engine remains visible. If another d4 query engine is added,
only its construction changes:

```python
engine = queries.wrap_queries(D4DecDnnfRsEngine(target))
```

## `CompilationContext`

`CompilationContext` always has a formula. It has no target vocabulary index
and no query-alignment methods.

```python
class CompilationContext:
    def __init__(
        self,
        phi: FNode,
        project_on: Iterable[FNode] | None = None,
        env: Environment | None = None,
    ) -> None:
        self._env = env if env is not None else get_env()
        self._normalizer = NormalizerWalker(self._env)
        self.phi = self.normalize(phi)

        atoms = self.phi.get_atoms() if project_on is None else project_on
        self.project_on = [self._normalize_atom(atom) for atom in atoms]

    def normalize(self, formula: FNode) -> FNode:
        return self._normalizer.normalize(formula)

    def _normalize_atom(self, atom: FNode) -> FNode:
        normalized = self.normalize(atom)
        return normalized.arg(0) if normalized.is_not() else normalized
```

Constructor behavior:

- `phi` is required and normalized immediately.
- Explicit projection atoms are normalized immediately.
- Without explicit projection, `project_on` comes from normalized `phi` atoms.
- Projection atoms use positive canonical representatives; their literal
  polarity is irrelevant to variable projection.
- External formulas or lemmas can be normalized through `normalize()`.

Public compilation methods:

```python
def compile_treduced(
    self,
    compiler_type: type[PropCompiler[T_Target]],
    lemmas: Iterable[FNode],
) -> TheoryCompiledTarget[T_Target]:
    normalized_lemmas = [self.normalize(lemma) for lemma in lemmas]
    abstractor = Abstractor()
    compiler = compiler_type(abstractor)
    return TReducedBuilder(compiler, env=self._env).build(
        self.phi,
        normalized_lemmas,
        abstractor,
        project_on=self.project_on,
    )
```

`compile_textended()` follows the same pattern with `TExtendedBuilder`.

Compile methods do not mutate the context or add query state. Lemmas remain
explicit method arguments so reusing a context cannot accidentally reuse stale
lemmas.

## `QueryContext`

`QueryContext` always has a complete target-vocabulary index. Here, target
vocabulary means the exact SMT atoms in `target.projection_atoms`. It has no
`phi`, `project_on`, lemmas, or compilation methods.

Prefer its constructor over a `from_target()` or `build()` classmethod:

```python
class QueryContext:
    def __init__(
        self,
        target: TheoryCompiledTarget[Any],
        env: Environment | None = None,
    ) -> None:
        self._normalizer = NormalizerWalker(env)
        self._atom_index = self._index_atoms(target.projection_atoms)
```

No optional index state exists. A query context cannot be constructed without
exact target `projection_atoms`, and query alignment never falls back to unverified
canonical atoms.

### Target Vocabulary Index

Use one dictionary. Its value tuple contains the exact compiled atom and
whether normalizing that compiled atom produced a negated canonical atom:

```python
def _index_atoms(
    self,
    atoms: Iterable[FNode],
) -> dict[FNode, tuple[FNode, bool]]:
    index: dict[FNode, tuple[FNode, bool]] = {}

    for target_atom in atoms:
        canonical, target_negated = self._normalize_with_polarity(target_atom)

        previous = index.get(canonical)
        if previous is not None and previous[0] != target_atom:
            raise ValueError(
                f"Ambiguous normalized atom {canonical}: "
                f"{previous[0]}, {target_atom}"
            )

        index[canonical] = (target_atom, target_negated)

    return index
```

Reject distinct compiled atoms with the same canonical key. Otherwise query
alignment would have no unique target variable.

### Literal Alignment

Normalize each complete assumption literal. Then combine its normalized
polarity with the polarity of the exact target atom:

```python
def _align_literal(self, literal: FNode) -> FNode:
    canonical, query_negated = self._normalize_with_polarity(literal)

    try:
        target_atom, target_negated = self._atom_index[canonical]
    except KeyError as exc:
        raise ValueError(
            f"Query atom not in target projection_atoms: {literal.serialize()}"
        ) from exc

    aligned_negated = query_negated ^ target_negated
    if aligned_negated:
        return self._normalizer.mgr.Not(target_atom)
    return target_atom
```

For example, `x < y` may normalize to `Not(y <= x)`. XOR preserves its
meaning whether the query, compiled target, or both use that representation.

`align_assumptions()` maps a list through `_align_literal()` and preserves
`None` exactly.

### Formula Alignment

For clauses and cubes:

1. Normalize the complete query formula.
2. Collect canonical atoms from the normalized formula.
3. Look up every atom in `_atom_index`.
4. Substitute the exact compiled atom, negating it when `target_negated` is
   true.
5. Pass the rebuilt formula to the raw engine.

Complete-formula normalization already preserves query-side Boolean polarity.
Substitution only compensates for target-side polarity.

Raw engines continue to validate clause and cube shape through existing
`clause_lits()` and `cube_lits()` helpers.

Unknown atoms fail before backend delegation with:

```text
ValueError: Query atom not in target projection_atoms: ...
```

### Query Wrapping

```python
def wrap_queries(
    self,
    engine: QueryEngine[T_Target],
) -> QueryEngine[T_Target]:
    return NormalizingQueryEngine(engine, self)
```

Caller must construct the raw engine and `QueryContext` from the same target.
Keep this explicit instead of adding another engine factory abstraction.

## `NormalizingQueryEngine`

This thin adapter implements `QueryEngine` and delegates backend work:

Runtime imports flow from `context` to `queries.normalizing`. The adapter uses
deferred annotations and imports `QueryContext` only under `TYPE_CHECKING`, so
the reverse dependency never exists at runtime. Do not use local imports to
hide this dependency.

```python
class NormalizingQueryEngine(QueryEngine[T_Target], Generic[T_Target]):
    def __init__(
        self,
        inner: QueryEngine[T_Target],
        context: QueryContext,
    ) -> None:
        self._inner = inner
        self._context = context

    def is_satisfiable(self, assumptions=None) -> bool:
        return self._inner.is_satisfiable(
            self._context.align_assumptions(assumptions)
        )

    def count_truth_assignments(self, assumptions=None) -> int:
        return self._inner.count_truth_assignments(
            self._context.align_assumptions(assumptions)
        )

    def entails_clause(self, query_clause: FNode) -> bool:
        return self._inner.entails_clause(
            self._context.align_formula(query_clause)
        )

    def is_implicant(self, query_cube: FNode) -> bool:
        return self._inner.is_implicant(
            self._context.align_formula(query_cube)
        )

    def is_valid(self) -> bool:
        return self._inner.is_valid()

    def enumerate_truth_assignments(self):
        return self._inner.enumerate_truth_assignments()
```

`is_valid()` and `enumerate_truth_assignments()` require no query alignment and
delegate unchanged. Enumerated assignments remain keyed by compiled care
variables.

To make protocol conformance structural, remove `__init__` from the
`QueryEngine` protocol. Constructors are not part of query behavior, and raw
engines and wrappers legitimately have different constructors.

## Persistence

Do not persist either context.

`TheoryCompiledTarget.save()` already stores:

- abstraction mapping;
- projection-atom IDs;
- backend artifact.

This is sufficient for `QueryContext(target, env=env)` to rebuild its index
after load. `TheoryCompiledTarget.load(..., env=env)` forwards the environment
to abstraction deserialization, keeping loaded atoms in the same PySMT
environment as subsequent queries. No normalizer instance or query index needs
serialization.

The normalization algorithm is treated as a library-wide invariant. Persisting
a normalization-policy version remains out of scope unless multiple policies
are introduced later.

## Package Layout And Exports

Keep both public contexts in `tddnnf/context.py` while they remain small:

```text
tddnnf/context.py
    CompilationContext
    QueryContext

tddnnf/queries/normalizing.py
    NormalizingQueryEngine
```

Export only the public contexts at package top level:

```python
from tddnnf.context import CompilationContext, QueryContext

__all__ = ["CompilationContext", "QueryContext"]
```

`NormalizingQueryEngine` remains importable from its module but is not added to
top-level exports.

Remove `KCMTContext` rather than retaining a compatibility alias unless a
released public version already requires deprecation support.

## Implementation Phases

### Phase 1: Split Existing Context State

Deliverables:

- Replace `KCMTContext` with `CompilationContext` and `QueryContext`.
- Move formula and projection normalization into `CompilationContext`.
- Move target indexing and alignment into `QueryContext`.
- Build query index in `QueryContext.__init__`.
- Store `(compiled_atom, target_negated)` together in one dictionary.
- Update `NormalizingQueryEngine` to depend on `QueryContext`.
- Remove `__init__` from the `QueryEngine` protocol.
- Export both contexts from `tddnnf.__init__`.

Acceptance criteria:

- Neither context contains optional mode-dependent state.
- `CompilationContext` cannot exist without `phi`.
- `QueryContext` cannot exist without a target.
- Query alignment never proceeds without a target index.
- Raw query engines remain unchanged.

Tests:

- Formula is normalized during `CompilationContext` construction.
- Default and explicit projection atoms are normalized.
- `QueryContext(target)` indexes target projection atoms.
- Ambiguous canonical target atoms are rejected.
- Equivalent raw assumptions align to compiled atoms.
- Normalization-induced polarity flips are preserved.
- Nested clauses and cubes align correctly.
- Unknown query atoms fail before backend delegation.
- `None` assumptions remain `None`.
- No-input query methods delegate unchanged.

### Phase 2: Add Context-Owned Compilation

Deliverables:

- Implement `CompilationContext.compile_treduced()`.
- Implement `CompilationContext.compile_textended()`.
- Keep existing builder APIs unchanged.

Acceptance criteria:

- Caller does not construct `Abstractor` or compiler instance manually.
- Compile methods defensively normalize lemmas.
- Returned target contains normalized projection atoms.
- Compilation does not add query state to `CompilationContext`.
- Same-process queries use a new `QueryContext(target)`.

Tests:

- Compile simple examples through both strategies.
- Compare results with existing manual builder flow.
- Query direct target and save/loaded target through fresh query contexts.

### Phase 3: Update Examples And Testbench

Deliverables:

- Update examples to use `CompilationContext` and `QueryContext`.
- Update testbench query task in a separate change.
- Remove duplicated testbench normalization and alignment helpers.

Acceptance criteria:

- Examples still choose compiler and raw query engine explicitly.
- Online lemma enumeration uses normalized compilation inputs.
- Separate-process query tasks pass raw queries directly to wrapped engines.
- Existing logs and result schemas remain unchanged.

Verification:

- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff format . --check`
- `uv run basedpyright tddnnf/`

## Non-Goals

- Do not serialize either context.
- Do not serialize normalizer internals or query indexes.
- Do not introduce private vocabulary or atom-alignment classes.
- Do not hide backend selection behind string names.
- Do not add an engine factory abstraction.
- Do not force lemma enumeration into compilation.
- Do not modify raw backend engines.
- Do not remove low-level builders or compiler APIs.
