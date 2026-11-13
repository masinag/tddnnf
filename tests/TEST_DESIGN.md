# Test design plan

This file proposes test boundaries and responsibilities;
the exact cases and expected behavior will be agreed one group at a time before
implementing tests.

## Scope

This plan covers the `tddnnf` library in `/tmp/tddnnf-06-public-migration`,
including its current public migration: `TheoryCompilation` and
`TheoryCompiledTarget`. Benchmark harness tests are outside this plan.

The test tree below is proposed, except for the implemented core groups,
`tests/unit/core/test_abstraction.py` and `tests/unit/core/test_pysmt_utils.py`.
The removed suite remains unreplaced elsewhere; further cases will be decided
one group at a time.

### Implemented Abstractor group

Tests use the function-scoped `env` fixture in `tests/conftest.py`, which enters
an isolated PySMT environment and restores the previous environment on cleanup.
Atoms stay local to `test_abstraction.py`: Boolean `p` and `q`,
real `x <= 0`, and integer `n = 1`. They cover empty mappings, stable registration,
distinct and sparse IDs, membership, bidirectional lookup, constructor copying,
and read-only live mapping views. Nonpositive lookup IDs raise `ValueError`;
unknown positive IDs raise `KeyError`.

Empty and populated serialization round trips preserve atoms and IDs in default
and explicit destination environments. Assertions compare destination formulas,
not exact SMT-LIB text. Boolean constants (`True` and `False`) raise `ValueError`
in constructor mappings, `get_id()`, and `from_dict()`, including standalone
constant scripts. Deserialization reuses constructor validation, and failed
registrations leave both maps, counts, and subsequent ID allocation unchanged.
The shared `is_atom()` predicate remains unchanged.

No shared formula bank or backend fixtures are introduced yet. Broader malformed
mapping validation, other core modules, and backend tests remain deferred.

### Implemented PySMT utility group

`test_pysmt_utils.py` uses `env`, local formulas, and small tables with explicit
expected results. Classification covers symbols, theory relations, constants,
negations, nested and mixed connectives, and non-Boolean terms. Theory-atom
filtering preserves constants, order, duplicates, and its input.

Query tests cover empty lists, stable deduplication, polarity, constants and
negated constants, complementary literals, and invalid or undeclared inputs.
Validation continues after decisive constants and complementary pairs. Vocabulary
tests cover declaration order, unused atoms, constant formulas, both quantifier
kinds, invalid/duplicate declarations, missing atoms, and mixed quantifiers.
Representative successful and rejected calls check that inputs remain unchanged.

Type checking is suspended and restored on normal and exceptional exits in
default and explicit environments. Tests use public formula construction and
verify that explicit selection leaves the current environment's checking active.
Production behavior and backend validation remain outside this group.

## Organization

- Use pytest, with one module per class or cohesive group of classes.
- Write shared contract tests once and parametrize them over implementations.
  Avoid inherited test base classes and copied suites for each backend.
- Parametrize formula-dependent behavior over a small, named formula corpus.
  Each test selects relevant cases; do not multiply every test by every formula,
  compilation mode, and backend.
- Keep implementation-specific behavior in separate modules.
- Test observable results and documented errors. Avoid assertions about private
  call sequences, incidental serialization order, or exact timings.
- Use small real objects inside the unit under test. Use a simple fake at an
  adjacent boundary when needed, such as a recording compiler for pipeline tests.
  Semantic tests of native backends must exercise those backends.
- Keep full compile/save/load/query workflows in a small integration suite.

## Proposed directory structure

```text
tests/
├── conftest.py
├── cases/
│   └── formulas.py
├── unit/
│   ├── core/
│   │   ├── test_abstraction.py
│   │   ├── test_pysmt_utils.py
│   │   ├── test_theory_compiled_target.py
│   │   ├── test_persistence.py
│   │   └── test_stats_collector.py
│   ├── normalization/
│   │   └── test_normalizer.py
│   ├── compilers/
│   │   ├── test_compiler_contract.py
│   │   ├── test_target_contract.py
│   │   ├── test_cudd.py
│   │   ├── test_pysdd.py
│   │   └── test_d4.py
│   ├── queries/
│   │   ├── test_engine_contract.py
│   │   ├── test_session.py
│   │   ├── test_bdd_engine.py
│   │   ├── test_sdd_engine.py
│   │   └── test_ddnnife_engine.py
│   └── test_theory_compilation.py
└── integration/
    └── test_compilation_workflow.py
```

Backend-specific modules are only needed where behavior is genuinely specific;
omit empty modules. No separate tests for protocol declarations or trivial data
holders such as `DagSize`; exercise their contracts through implementations.

### Shared support

| File                | Responsibility                                                                                                                                                                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `conftest.py`       | Isolated PySMT environments; compiler/target/engine fixtures with readable backend IDs; native-resource cleanup; temporary artifact directories. Keep backend imports local so an unavailable optional dependency does not prevent unrelated tests from collecting. |
| `cases/formulas.py` | Named formula factories and independently specified expectations. Construct FNodes in the current test environment rather than storing global FNodes. Store only case data actually shared by multiple modules.                                                     |

### Core and normalization

| File                             | Classes/group and proposed coverage                                                                                                                                                                                                                                                      |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_abstraction.py`            | `Abstractor`: stable bidirectional IDs, repeated registration, supplied mappings, serialization round trips, reconstruction in an explicit environment.                                                                                                                                  |
| `test_pysmt_utils.py`            | Atom/literal/clause/cube predicates; flat query-literal validation and simplification; duplicates, constants, complementary literals, unknown projection atoms; compilation vocabulary validation and retained order. `SuspendTypeChecking`: restoration on normal and exceptional exit. |
| `test_theory_compiled_target.py` | `TheoryCompiledTarget`: association of target, abstraction, projection, and environment; delegation of reconstruction/size; creation of independent query sessions. Use small fakes where backend semantics are irrelevant.                                                              |
| `test_persistence.py`            | Shared artifact helpers: metadata version checks, malformed or missing metadata, successful atomic save, cleanup after failure, refusal to overwrite an existing destination.                                                                                                            |
| `test_stats_collector.py`        | `StatsCollector`: behavior with/without a supplied logger, recorded values, timed regions using a controlled clock. Agree exception behavior before asserting it.                                                                                                                        |
| `test_normalizer.py`             | `NormalizerWalker`: semantic preservation, canonicalization of equivalent supported theory atoms, polarity, idempotence, Boolean structure, explicit environment, close/context-manager behavior. Parametrize by formula family.                                                         |

### Compilers and targets

| File                        | Classes/group and proposed coverage                                                                                                                                                                                                                                                                                                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_compiler_contract.py` | `BddCompiler`, `SddCompiler`, `D4Compiler`: compile Boolean structure and abstract theory atoms; preserve meaning; respect declared vocabulary and retained-variable order; existential or universal elimination; reject invalid declarations and requests mixing both quantifier kinds. Parametrize backend × relevant formula/quantification case. |
| `test_target_contract.py`   | `BddCompiledTarget`, `SddCompiledTarget`, `D4CompiledTarget`: `to_pysmt` equivalence, save/load preservation of meaning and mappings, size metrics on deliberately tiny known DAGs. Do not expect different representations to have identical sizes or serialized bytes.                                                                             |
| `test_cudd.py`              | BDD-specific translation/representation cases, complemented edges, manager ownership, and persistence behavior not covered by shared contracts.                                                                                                                                                                                                      |
| `test_pysdd.py`             | SDD-specific translation/representation cases, variable remapping, vtree/configuration behavior, and native-node ownership.                                                                                                                                                                                                                          |
| `test_d4.py`                | BCS12 translation, d4 output parsing/cleanup and remapping, constant circuits, subprocess failures and missing executable. Mock the process only for process/error handling; use real d4 in semantic contract tests.                                                                                                                                 |

### Query engines and sessions

| File                      | Classes/group and proposed coverage                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_engine_contract.py` | `BddEngine`, `SddEngine`, `DdnnifeEngine`: satisfiability, validity, counting, clause entailment, implicant checking, enumeration, assumptions, and query input validation. Include empty/constant queries, duplicates, contradictory assumptions, tautological clauses, and declared projection dimensions absent from the DAG. Check that sequential queries do not change the target. |
| `test_session.py`         | `QuerySession`: normalization/alignment of public query inputs, polarity, rejection of atoms outside the projection, environment binding, independent sessions and generators, context-manager exit, repeated close, use after close, cleanup of active enumeration. Use a small engine fake for wrapper behavior.                                                                       |
| `test_bdd_engine.py`      | Any BDD-specific restriction, complemented-root, enumeration, or ownership regressions that cannot be expressed as shared contract cases.                                                                                                                                                                                                                                                |
| `test_sdd_engine.py`      | Any SDD-specific conditioning, counting, enumeration, or ownership regressions that cannot be expressed as shared contract cases.                                                                                                                                                                                                                                                        |
| `test_ddnnife_engine.py`  | Native ddnnife loading, remapped signed literals, temporary-file cleanup on success/failure, incompatible target types, and explicitly unsupported circuit cases.                                                                                                                                                                                                                        |

Raw engines accept flat aligned literal lists; `QuerySession` accepts the public
formula forms. Test these as distinct boundaries. Enumeration expectations should
compare complete assignments without assuming enumeration order; projection key
order can be checked where promised by the interface.

### Compilation orchestration

| File                           | Classes/group and proposed coverage                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_theory_compilation.py`   | `TheoryCompilation`: input normalization; default/explicit atom vocabulary; required inclusion of all normalized formula atoms; extra query atoms and absent free dimensions; deduplication and constant normalization; lemma-only generated atoms; compiler-instance validation; supplied abstractor; reduced versus extended construction and quantifier selection; metrics and lifecycle. An explicit empty vocabulary is valid only when the normalized formula has no atoms. Use a recording compiler to inspect the public compiler request without invoking native backends. |
| `test_compilation_workflow.py` | A few real normalize → compile → save → load → query workflows, including projection and generated lemma atoms. Parametrize compatible backend pairs and reduced/extended constructions only where their expected semantics have been defined.                                                                                                                                                                                                                                                                                                                                      |

## Parametrization and expected results

Start with formula categories, then agree concrete formulas interactively:

| Case family                                                    | Intended purpose                                                               |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `true`, `false`, zero-dimensional projection                   | Constants, empty vocabulary, counts of one or zero.                            |
| One atom and its negation                                      | Polarity, assumptions, basic counts and queries.                               |
| Small conjunction/disjunction and other supported connectives  | Translation and independently enumerable models.                               |
| Shared subexpressions                                          | DAG traversal and reconstruction.                                              |
| Declared but unused atoms                                      | Counting/enumeration over the declared projection.                             |
| Explicit vocabulary and empty vocabulary for constant formulas | Complete-vocabulary validation, extra dimensions, and zero-dimensional counts. |
| Existential/universal variables                                | Correct elimination semantics; reject mixed quantifier kinds.                  |
| Theory atoms and equivalent syntactic forms                    | Abstraction, normalization, and query alignment.                               |
| Lemmas with additional atoms                                   | Reduced/extended construction and generated-variable elimination.              |

For small propositional cases, use explicit truth tables or exhaustive assignment
evaluation as the oracle. For quantified cases, evaluate existential or universal elimination
independently. At the propositional compiler/engine layer, theory atoms are
independent Boolean dimensions; do not silently replace Boolean model counts
with counts of theory-consistent assignments. Normalization equivalence and
theory workflows may use an SMT solver as an independent oracle.

Parametrize engines over compatible `(compiler, target, engine)` combinations,
not arbitrary compiler × engine pairs. The current library has BDD/CUDD,
SDD/PySDD, and d4/ddnnife combinations.

Maintain explicit supported-operation/case information alongside backend fixtures
only where implementations differ. An unsupported operation needs its own test
of the agreed rejection behavior. Exclude it from successful-result cases with a
specific reason; never catch arbitrary exceptions and turn them into skips.
Use dependency skips only for genuinely unavailable optional tools. Known bugs
may use narrow `xfail(strict=True)` cases with a reason; missing dependencies and
unsupported operations are not bugs.

## Interactive implementation order

1. Agree the directory layout and unit/integration boundaries.
2. Agree the initial formula cases and backend capability differences.
3. Specify and implement core utilities and normalization tests.
4. Specify and implement the shared compiler and target contracts.
5. Specify and implement the shared engine contract and session tests.
6. Cover compilation orchestration and the few integration workflows.

At each step, agree inputs, expected outputs/errors, parametrization axes, and
dependencies before adding tests. The coverage descriptions above are candidates,
not a commitment to every listed case or to today's incidental behavior.
