# KCMTContext Ergonomic API Implementation Plan

## High-Level Idea

Introduce `KCMTContext` as the single user-facing object that owns normalization
and workflow ergonomics for theory knowledge compilation modulo theories.

The existing low-level pieces stay meaningful:

- Builders construct T-reduced or T-extended formulas.
- Compilers produce concrete artifacts such as d-DNNF, SDD, or BDD targets.
- Query engines stay explicit backend-specific classes.
- `TheoryCompiledTarget` remains the persisted artifact plus abstraction and
  care-variable vocabulary.

`KCMTContext` sits above them and removes repetitive manual wiring:

- It normalizes `phi`, optional projection atoms, externally supplied lemmas,
  and query inputs.
- If no projection atoms are provided, `ctx.project_on` defaults to the atoms of
  normalized `phi`.
- It owns the normalized compilation state when compiling in one process.
- It can be restored from a loaded `TheoryCompiledTarget` in a later process.
- It wraps an explicit query engine with query normalization and atom alignment.
- Lemmas are passed explicitly to compilation methods, making it clear that they
  must be computed or loaded before compilation.

Important design rule:

```text
Compilation context and query context do not need to be the same object.
They only need to agree through the persisted normalized compiled vocabulary.
```

So no normalizer state or normalization policy metadata is persisted. The target
already stores the abstraction and care vars. Query-time context rebuilds an
index from that vocabulary.

## New Interface Examples

The numbered implementation phases below describe incremental delivery, not
runtime lifecycle stages. The separate-script examples are workflow steps.

### Single Script: Lemma Enumeration, Compilation, Queries

```python
from pysmt.shortcuts import GT, And, Not, Or, Plus, Real, Symbol
from pysmt.typing import REAL
from tlemma_enum.solvers.mathsat_total import MathSATTotalEnumerator

from tddnnf.context import KCMTContext
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

ctx = KCMTContext(phi)

enumerator = MathSATTotalEnumerator()
enumerator.check_all_sat(ctx.phi, atoms=ctx.project_on)
lemmas = enumerator.get_theory_lemmas()

target = ctx.compile_treduced(D4Compiler, lemmas=lemmas)
engine = ctx.wrap_queries(D4Engine(target))

print(engine.is_satisfiable(assumptions))
print(engine.entails_clause(clause))
print(engine.count_truth_assignments())
for model in engine.enumerate_truth_assignments():
    print(model)
```

### Workflow Step 1: Lemma Enumeration

This script reads raw input formula, normalizes it once through `KCMTContext`,
computes lemmas from the normalized formula and its normalized atoms, and writes
those lemmas for later compilation. The enumerator output is expected to already
be normalized because its inputs are normalized.

```python
from pathlib import Path

from pysmt.shortcuts import And, read_smtlib, write_smtlib
from tlemma_enum.solvers.mathsat_total import MathSATTotalEnumerator

from tddnnf.context import KCMTContext

formula_path = Path("formula.smt2")
lemmas_path = Path("lemmas.smt2")

phi = read_smtlib(str(formula_path))

ctx = KCMTContext(phi)

enumerator = MathSATTotalEnumerator()
enumerator.check_all_sat(ctx.phi, atoms=ctx.project_on)

lemmas = enumerator.get_theory_lemmas()
write_smtlib(And(lemmas), lemmas_path)
```

When no `project_on` is passed, `ctx.project_on` is derived from
`ctx.phi.get_atoms()`.

### Workflow Step 2: Compilation From Stored Lemmas

This script reads raw formula and stored lemmas, normalizes the formula through
a new context, uses normalized formula atoms as projection atoms by default,
defensively normalizes the loaded lemmas inside compilation, and saves the
target.

```python
from pathlib import Path

from pysmt.fnode import FNode
from pysmt.shortcuts import read_smtlib

from tddnnf.context import KCMTContext
from tddnnf.compilers.d4 import D4Compiler

formula_path = Path("formula.smt2")
lemmas_path = Path("lemmas.smt2")
output_dir = Path("compiled-ddnnf")


def split_lemmas(node: FNode) -> list[FNode]:
    return list(node.args()) if node.is_and() else [node]

phi = read_smtlib(str(formula_path))
lemmas = split_lemmas(read_smtlib(str(lemmas_path)))

ctx = KCMTContext(phi)

target = ctx.compile_treduced(D4Compiler, lemmas=lemmas)
target.save(output_dir)
```

### Workflow Step 3: Queries In A Later Session

This script loads only the compiled target and query files. It does not need the
original `KCMTContext` instance from compilation.

```python
from pathlib import Path

from pysmt.shortcuts import read_smtlib

from tddnnf.context import KCMTContext
from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.queries.d4_engine import D4Engine

source = Path("compiled-ddnnf")
query_file = Path("query.smt2")

target = TheoryCompiledTarget.load(source, D4CompiledTarget)

ctx = KCMTContext.from_target(target)
engine = ctx.wrap_queries(D4Engine(target))

query = read_smtlib(str(query_file))
print(engine.is_implicant(query))
```

For multiple future d4 query engines, only the explicit engine class changes:

```python
engine = ctx.wrap_queries(D4DecDnnfRsEngine(target))
```

## Detailed Implementation Details

### `KCMTContext`

Add `tddnnf/context.py`.

Core shape:

```python
from __future__ import annotations

from collections.abc import Iterable
from pysmt.fnode import FNode

from tddnnf.normalization.normalizer import NormalizerWalker


class KCMTContext:
    def __init__(
        self,
        phi: FNode | None = None,
        project_on: Iterable[FNode] | None = None,
        normalizer: NormalizerWalker | None = None,
    ) -> None:
        self._normalizer = normalizer or NormalizerWalker()
        self.phi = self.normalize(phi) if phi is not None else None
        if project_on is not None:
            self.project_on = [self._normalize_atom(atom) for atom in project_on]
        elif self.phi is not None:
            self.project_on = [self._normalize_atom(atom) for atom in self.phi.get_atoms()]
        else:
            self.project_on = None
```

Phase 1 public method:

- `normalize(formula: FNode) -> FNode`

Atom canonicalization stays private as
`_normalize_atom(atom: FNode) -> FNode`. Collection mapping helpers are not
part of the public API; callers normalize an external formula or lemma through
`normalize` directly.

Later phases add these public workflow methods:

- `compile_treduced(compiler_type: type[PropCompiler[T_Target]], *, lemmas: Iterable[FNode]) -> TheoryCompiledTarget[T_Target]`
- `compile_textended(compiler_type: type[PropCompiler[T_Target]], *, lemmas: Iterable[FNode]) -> TheoryCompiledTarget[T_Target]`
- `from_target(target: TheoryCompiledTarget[Any]) -> KCMTContext`
- `wrap_queries(engine: QueryEngine[T_Target]) -> QueryEngine[T_Target]`

Behavior:

- Constructor normalizes `phi` immediately.
- If `project_on` is provided, constructor normalizes those atoms.
- If `project_on` is omitted and `phi` is provided, constructor sets
  `project_on` to normalized atoms from normalized `phi`.
- `compile_treduced` and `compile_textended` require `self.phi is not None`.
- Compile methods defensively normalize the provided lemmas immediately before
  invoking the builder. Lemmas produced online from `ctx.phi` and
  `ctx.project_on` should already be normalized; loaded/external lemmas may not
  be.
- Compile methods create a fresh `Abstractor`, instantiate the compiler with
  that abstractor, and delegate to existing builder logic.
- Phase 2 adds `from_target` together with the target vocabulary index and query
  alignment that consume that index.

### Atom Normalization And Alignment

`_normalize_atom` must handle the current awkward example pattern:

```python
normalized = normalizer.normalize(atom)
atom = normalized.arg(0) if normalized.is_not() else normalized
```

This means projection atoms and query atoms always become positive canonical
atoms. Query literal polarity is preserved separately.

Build target-derived index:

```python
def _build_atom_index(self, atoms: Iterable[FNode]) -> dict[FNode, FNode]:
    index: dict[FNode, FNode] = {}
    for atom in atoms:
        normalized = self._normalize_atom(atom)
        previous = index.get(normalized)
        if previous is not None and previous != atom:
            raise ValueError(f"Ambiguous normalized atom {normalized}: {previous}, {atom}")
        index[normalized] = atom
    return index
```

Align query literal:

```python
def _align_literal(self, literal: FNode) -> FNode:
    is_neg = literal.is_not()
    atom = literal.arg(0) if is_neg else literal
    normalized = self._normalize_atom(atom)

    if self._atom_index is None:
        compiled_atom = normalized
    else:
        try:
            compiled_atom = self._atom_index[normalized]
        except KeyError as exc:
            raise ValueError(f"Query atom not in compiled vocabulary: {atom.serialize()}") from exc

    return self._normalizer.mgr.Not(compiled_atom) if is_neg else compiled_atom
```

Query alignment methods remain private implementation details unless later
usage demonstrates a need for public access. For same-process compilation and
querying, Phase 3 compile methods rebuild the Phase 2 index by setting
`self._atom_index = self._build_atom_index(target.care_vars)` before returning.

### Formula Alignment Walker

Add a small walker or recursive helper for query formulas:

- Constants stay unchanged.
- Boolean symbols and theory atoms are normalized and aligned.
- `Not(atom)` is aligned as a literal.
- `And`, `Or`, and nested Boolean structures are rebuilt recursively.
- Unsupported structures can fall back to `self.normalize(formula)` first, then
  align atoms in the normalized formula.

This keeps `entails_clause(clause)` and `is_implicant(cube)` ergonomic. The raw
query engines still receive formulas compatible with existing `clause_lits` and
`cube_lits`.

### `NormalizingQueryEngine`

Add `tddnnf/queries/normalizing.py`.

It implements the existing `QueryEngine` protocol and delegates to an explicit
raw engine.

```python
class NormalizingQueryEngine(Generic[T_Target]):
    def __init__(self, inner: QueryEngine[T_Target], context: KCMTContext) -> None:
        self._inner = inner
        self._context = context

    def is_satisfiable(self, assumptions: list[FNode] | None = None) -> bool:
        return self._inner.is_satisfiable(self._context._align_literals(assumptions))

    def count_truth_assignments(self, assumptions: list[FNode] | None = None) -> int:
        return self._inner.count_truth_assignments(self._context._align_literals(assumptions))

    def is_valid(self) -> bool:
        return self._inner.is_valid()

    def entails_clause(self, query_clause: FNode) -> bool:
        return self._inner.entails_clause(self._context._align_formula(query_clause))

    def is_implicant(self, query_cube: FNode) -> bool:
        return self._inner.is_implicant(self._context._align_formula(query_cube))

    def enumerate_truth_assignments(self):
        return self._inner.enumerate_truth_assignments()
```

To avoid import cycles, `KCMTContext.wrap_queries` can import
`NormalizingQueryEngine` locally inside the method.

### Compilation Ergonomics

Keep low-level builder behavior available, but add context-owned compile methods
first. This avoids a large breaking change in one step.

Initial implementation:

```python
def compile_treduced(
    self,
    compiler_type: type[PropCompiler[T_Target]],
    *,
    lemmas: Iterable[FNode],
) -> TheoryCompiledTarget[T_Target]:
    if self.phi is None:
        raise ValueError("Cannot compile without phi")
    normalized_lemmas = [self.normalize(lemma) for lemma in lemmas]
    abstractor = Abstractor()
    compiler = compiler_type(abstractor)
    target = TReducedBuilder(compiler).build(
        self.phi,
        normalized_lemmas,
        abstractor,
        project_on=self.project_on,
    )
    self._atom_index = self._build_atom_index(target.care_vars)
    return target
```

Same pattern for `compile_textended`, using `TExtendedBuilder`.

Lemmas are intentionally not stored on the context by default. This makes the
compile call self-documenting:

```python
target = ctx.compile_treduced(D4Compiler, lemmas=lemmas)
```

and avoids stale lemma state if a user reuses one context for multiple
experiments.

For online lemma enumeration, no ex-post normalization step is needed before the
user receives the lemmas:

```python
enumerator.check_all_sat(ctx.phi, atoms=ctx.project_on)
lemmas = enumerator.get_theory_lemmas()
target = ctx.compile_treduced(D4Compiler, lemmas=lemmas)
```

The compile method still normalizes `lemmas` as a cheap safety boundary for
stored or externally generated lemma lists.

Later optional cleanup:

- Add `TReducedBuilder.build_context(ctx)` or make builders accept
  `KCMTContext`.
- Remove explicit `Abstractor` from examples.
- Keep direct builder API for advanced users and tests.

### Persistence

Do not change persisted schema unless needed.

Current `TheoryCompiledTarget.save` already persists:

- abstraction mapping
- care variable ids
- backend target artifact

This is enough, provided compilation stored normalized atoms in `Abstractor` and
`care_vars`. `KCMTContext` compile methods enforce that.

Query restore:

```python
target = TheoryCompiledTarget.load(path, D4CompiledTarget)
ctx = KCMTContext.from_target(target)
engine = ctx.wrap_queries(D4Engine(target))
```

### Testbench Cleanup Target

`../tddnnf-testbench/scripts/tasks/query_kc.py` can eventually remove:

- `_normalized_atom_index`
- `_align_assumptions`
- `_read_aligned_query_cube`
- direct `NormalizerWalker` import

Replacement shape:

```python
def _load_engine(source: Path, compiler: str) -> QueryEngine:
    target_type, engine_type = BACKENDS[compiler]
    target = TheoryCompiledTarget.load(source, target_type)
    ctx = KCMTContext.from_target(target)
    return ctx.wrap_queries(engine_type(target))
```

Then query files can be read and passed directly to wrapped engine methods.

## Implementation Phases

### Phase 1: Add Lean Context Normalization

Deliverables:

- Add `tddnnf/context.py`.
- Implement `KCMTContext.__init__`, public `normalize`, and private
  `_normalize_atom`.
- Export `KCMTContext` from `tddnnf/__init__.py`.

Acceptance criteria:

- `KCMTContext(phi)` produces normalized `ctx.phi` and defaults
  `ctx.project_on` to normalized atoms from `ctx.phi`.
- `KCMTContext(phi, project_on=atoms)` uses caller-supplied projection atoms
  after normalization.
- Online lemma enumeration over `ctx.phi` and `ctx.project_on` produces lemmas
  that are already normalized.
- `ctx.normalize(lemma)` remains available for callers that need to normalize
  an external formula explicitly.
- No target vocabulary index or collection normalization helpers are exposed
  before query alignment needs them.

Tests:

- Formula is normalized during construction.
- Default projection is derived from normalized formula atoms.
- Explicit projection atoms are normalized.
- External lemma is normalized through `ctx.normalize(lemma)`.

### Phase 2: Add Query Wrapper

Deliverables:

- Add `tddnnf/queries/normalizing.py`.
- Implement `NormalizingQueryEngine`.
- Implement `KCMTContext.from_target`, the target vocabulary index,
  `wrap_queries`, and private query alignment helpers.

Acceptance criteria:

- Raw query formulas can be passed to wrapped engine.
- `KCMTContext.from_target(target)` builds the index from loaded care vars.
- Wrapped engine delegates no-query methods unchanged.
- Unknown query atoms raise clear `ValueError`.
- Ambiguous normalized target atoms raise `ValueError`.

Tests:

- Wrapper calls inner engine with normalized/aligned assumptions.
- Wrapper aligns clauses and cubes.
- `is_valid` and `enumerate_truth_assignments` do not normalize anything.
- Fresh context indexes target care vars and rejects ambiguous normalized atoms.

### Phase 3: Add Context-Owned Compilation

Deliverables:

- Implement `KCMTContext.compile_treduced`.
- Implement `KCMTContext.compile_textended`.
- Keep existing builder API unchanged.

Acceptance criteria:

- User no longer needs to create `Abstractor`.
- User no longer needs to instantiate compiler manually.
- `ctx.compile_treduced(D4Compiler, lemmas=lemmas)` returns valid
  `TheoryCompiledTarget`.
- Returned target has normalized `care_vars`.
- Lemmas are defensively normalized inside the compile method, mainly for
  loaded/external lemma lists.
- Compile methods rebuild the target vocabulary index after context-owned
  compilation so same-process queries use the compiled vocabulary.

Tests:

- Compile simple example through `KCMTContext`.
- Compare query results against existing manual flow.
- Save/load target and query through fresh `KCMTContext.from_target`.

### Phase 4: Update Examples

Deliverables:

- Update `examples/ex-cimatti-tred.py` to use `KCMTContext`.
- Optionally update `examples/tred.py` and `examples/text.py`.

Acceptance criteria:

- Manual normalization block disappears from examples.
- Examples still choose query engine explicitly.
- Examples show online lemma enumeration without ex-post lemma normalization.

Tests:

- Run targeted examples if backend dependencies are available.
- Run `uv run pytest`.
- Run `uv run ruff check .`.
- Run `uv run basedpyright tddnnf/`.

### Phase 5: Testbench Migration

Deliverables:

- Update `../tddnnf-testbench/scripts/tasks/query_kc.py` in a separate change.
- Remove manual atom-index and assumption-alignment code.
- Use `KCMTContext.from_target(target).wrap_queries(engine)`.

Acceptance criteria:

- Query task works in a separate process from compilation.
- CE, CT, and IM query flows pass raw loaded query formulas/literals to wrapped
  engine.
- Existing logs/results schema unchanged.

Tests:

- Run one compile task, then one separate query task from persisted target.
- Confirm output logs match previous behavior on same benchmark.

### Phase 6: Optional API Polish

Deliverables:

- Add convenience aliases only after core API settles.
- Possible additions:
  - `ctx.query_engine(D4Engine, target)` as shorthand for wrapping.
  - IO helpers for lists of SMT-LIB formulas.
  - Builder methods accepting `KCMTContext` directly.

Acceptance criteria:

- No extra abstraction unless examples and testbench become visibly simpler.
- No removal of low-level API until compatibility needs are clear.

## Non-Goals

- Do not serialize `KCMTContext`.
- Do not serialize normalizer internals.
- Do not add normalization policy/version metadata.
- Do not hide query engine choice behind backend names.
- Do not force lemma enumeration into compilation; offline lemmas remain first
  class.
