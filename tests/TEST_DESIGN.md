# Test design plan

This file proposes test boundaries and responsibilities;
the exact cases and expected behavior will be agreed one group at a time before
implementing tests.

## Scope

This plan covers the `tddnnf` library in `/tmp/tddnnf-06-public-migration`,
including its current public migration: `TheoryCompilation` and
`TheoryCompiledTarget`. Benchmark harness tests are outside this plan.

The test tree below is proposed, except for the implemented core groups:
Abstractor, PySMT utilities, TheoryCompiledTarget, persistence, and StatsCollector, plus the normalization
and compilation input-ownership checks, compiler contracts, query-engine contracts,
QuerySession input and lifecycle contracts, and compilation orchestration described below.
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

This group uses no shared formula bank or backend fixtures. Broader malformed
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

### Implemented TheoryCompiledTarget group

Tests use `env`, local formulas, and one small conjunction-target fake. They
cover read-only bindings, copied atoms order, shared abstraction growth,
default and explicit environments, and reconstruction/size delegation.
Save/load preserves sparse IDs, later registrations, atoms order, the
selected target type, and destination environment. Reconstruction tests check
the returned formula and every descendant in default, explicit, and fresh load
environments, alongside reconstruction and size expectations. Explicit selection
leaves the globally active environment unchanged. A constant round trip covers
empty vocabulary and preservation of backend metadata and payloads.

Session creation and lifecycle belong to the QuerySession group. Native backends
remain deferred. Constructor input assertions
reject abstraction/atoms nodes from another manager, including identically
named nodes. These input checks are separate from output-ownership tests;
`to_pysmt()` has no runtime output-validation assertions.

### Implemented persistence group

`test_persistence.py` uses `tmp_path` and direct assertions for metadata round
trips, missing and unsupported schema versions (integer, string, Boolean, and
float), and propagation of missing-file and malformed-JSON errors. Saving tests
cover publication only after context exit, exception propagation and cleanup,
and refusal of an existing directory while preserving its contents. Assertions
avoid JSON formatting, exact error messages, and temporary directory names.
Mocks, shared fixtures, native backends, symlinks, concurrent saves, and other
metadata shapes remain outside this group.

### Implemented StatsCollector group

`test_stats_collector.py` covers operation without a logger, dictionary insertion
and replacement while preserving unrelated entries, nanosecond-to-second
conversion, accumulation across successive timed blocks, and elapsed-time
recording while propagating the same exception. Each timing test uses a local
controlled clock patched with `monkeypatch`, without sleeps or shared fixtures.
Invalid timing values, nested timing, backend metric keys, and additional clock
edge cases remain unverified.

### Implemented normalization and compilation ownership checks

Normalization tests check ownership of every result node for Boolean, integer,
real, constant, and negated formulas. Default and explicit environments retain
semantic equivalence and idempotence; equivalent arithmetic atoms share a
canonical form. An explicit environment differs from the active environment,
which remains unchanged.

Lifecycle tests use real normalizers and the existing `env` fixture to check
context-entry identity, closure after normal and exceptional exits, propagation
of the same exception, repeated close, and rejection of `walk()`, `normalize()`,
and context entry after close, including previously normalized Boolean input.
They assert public behavior without assuming an internal solver dependency.
Constructor failures, destructor behavior, internal resource-release counts, and
additional normalization semantics remain untested.

Input assertions reject foreign normalization roots, formulas, vocabulary entries,
lemmas, and supplied abstraction atoms before backend compilation. Identically
named nodes from distinct environments remain distinct inputs. Per the selected
manager-membership check, input assertions check supplied nodes only; foreign
descendants beneath a local root remain a caller precondition. Output tests still
inspect every descendant. Assertions are disabled under Python's `-O` mode.
### Implemented compiler contracts

`test_compiler.py` uses real BDD, SDD, and d4 backends with the existing
`env` fixture and shared formula factories from `tests/cases/formulas.py`, evaluated
inside that environment. The extraction preserves all 53 compiler cases and assertions. Plain
compilation covers eleven formulas: both constants, an atom and its negation,
conjunction, disjunction, implication, equivalence, Boolean ITE, a compound ITE,
and a five-symbol compound conjunction. Each formula's Boolean symbols are
pre-registered in a fresh Abstractor.

Existential elimination covers all three backends; universal elimination covers
BDD and SDD. Both use `p & (q | r)` eliminating `q` and the compound conjunction
eliminating `q, t`. Inputs remain quantifier-free; reconstruction is compared
against PySMT `Exists` or `ForAll`, and eliminated symbols must be absent from
its free variables. One separate test checks d4's `NotImplementedError` for
universal elimination. One Z3 helper checks unsatisfiability of the negated
biconditional for all successful compilation cases; `z3-solver` is a dev dependency.

The focused run reproduced an intermittent CUDD shutdown reference warning. A
read-only diagnostic found the BDD walker's bound-handler cycle retaining its
manager and memoized native nodes until garbage collection; collection while the
target remains alive exits cleanly. The full suite passed without that warning.
Production cleanup changes and broader resource lifecycle coverage remain deferred.

Theory atoms, unused vocabulary, elimination of all variables, sizes, metrics,
and queries remain deferred for this compiler group.

The same module covers nine native compile/save/load round trips:
BDD, SDD, and d4 crossed with `true`, `false`, and `p & (!q | r)`.
Formula factories run inside the existing `env` fixture. Vocabulary comes from
`get_atoms()`, with sparse abstraction IDs `7, 14, 21` assigned in symbol-name
order and an empty Abstractor for constants. Each backend saves beneath
`tmp_path` and loads through its native target class. Reconstruction uses the
original Abstractor and environment; an inline Z3 check proves equivalence by
finding the negated biconditional unsatisfiable.

Sizes, malformed or missing artifacts, fresh-environment loading, queries, and
lifecycle fixes remain deferred. Tests avoid serialized bytes and internal
metadata assertions and leave native cleanup warnings visible.

### Implemented query-engine contracts

`unit/queries/test_engine.py` parametrizes the compatible BDD/BddEngine,
SDD/SddEngine, and d4/DdnnifeEngine pairs over the shared eleven plain formulas
and one-/two-variable elimination cases. Formula construction happens inside
`env`; containers bind the retained atoms in the original declaration order.
Existential compilation covers all pairs, and universal compilation covers
BDD/SDD using the existing quantifier arguments. BDD/SDD include constant targets
and empty projections. ddnnife cannot load d4's constant circuits, and d4 does
not support universal elimination, so those combinations are omitted explicitly
from the successful-case table, without skips or xfails. An explicit group table
lists plain and existential cases for all three backends and universal cases for
BDD/SDD, with a named nonconstant plain subset for ddnnife. One loop builds engine,
literal-query, and assumption parameters together, unpacking each formula case
and creating its fixture input once. Constant factories are identified directly
by `TRUE`/`FALSE`; IDs only label cases.

Six tests cover satisfiability, validity, counting, clause entailment, implicants,
and enumeration. Query tables include empty lists, each polarity of the first
retained atom, complementary literals, all-positive/all-negative lists, and mixed
polarities. Satisfiability and counting also exercise omitted assumptions.
Constants use empty literal queries, plus the default-call case for assumptions.
These tables include satisfiable and unsatisfiable assumptions, tautological
clauses, and contradictory cubes.

All oracle helpers stay local to the engine module and use Z3. Quantified
expectations use `Exists`/`ForAll` on the original formulas. The model oracle
blocks complete assignments over retained atoms, including the empty projection;
counts come from those model sets. Enumeration compares the full model set,
rejects duplicates, checks Boolean values and projection key order, and agrees
with both Z3 and engine counts. Other operations use the corresponding Z3
satisfiability or counterexample query. No Python truth tables are introduced.
The fixture closes each engine at teardown; native cleanup warnings stay visible.

Engine malformed-input tables, dedicated lifecycle tests, backend-specific
coverage, unused vocabulary, theory workflows, and production fixes remain
deferred. Any newly discovered production bugs require a separate decision.

Verification: compiler collection and execution both preserve 53 cases; the
focused engine run passes 1,216 cases; the full suite passes 1,358 tests.
Repository-wide Ruff lint/format and tracked/new-file whitespace checks pass.
The generation simplification preserves every collected engine test ID and each
parameter's fixture input. Its focused and full reruns pass the same counts using
the main workspace interpreter; this worktree's `.venv` lacks the Z3 oracle.
The focused compiler run reproduced the known CUDD shutdown reference warnings;
the focused engine and full runs reported only PySMT walker deprecations. No new
production bugs surfaced. The consolidation commit's pyright hook was skipped
after it failed to resolve installed dependencies in this worktree, including
when retried with the workspace environment; Ruff commit hooks passed.

### Implemented QuerySession input and lifecycle contracts

`unit/queries/test_session.py` uses the real normalizer, the existing `env`
fixture and target, and one recording engine with fixed results and two fixed
assignments. Representative scenarios cover public return values, omitted/`None`/
empty assumptions, arithmetic alignment and reversed canonical polarity, nested
clause/cube flattening with order and duplicates, and constants. Compound
assumptions, non-formula inputs, and undeclared atoms after decisive constants
raise before delegation. Argument assertions focus on alignment and flattening.

Lifecycle scenarios cover normal/exceptional context exit, repeated close,
representative queries, enumeration creation and context re-entry after close,
independent sessions and enumerations, and stopping active/unstarted enumerations
on session closure. There are no lifecycle counters or failure subclasses.

Verification: all 10 focused session cases and all 1,368 suite cases pass using
the main workspace interpreter. Repository-wide Ruff lint/format, tracked/new-file
whitespace checks, and Pyright over production code and `test_session.py` pass
with the established dependency paths. PySMT walker deprecation warnings remain.

Detailed construction/cleanup failures, native resource release, constructor-input
rejection, environment isolation, and destructor behavior remain deferred. The
fake verifies wrapper behavior; native query correctness belongs to engine tests.
No production or public API changes were needed.

### Implemented compilation orchestration

`unit/test_theory_compilation.py` preserves the ten input-ownership cases and
adds nine orchestration cases using the real normalizer and local formulas.
Default vocabulary follows normalized node-ID order. Explicit vocabulary keeps
first-occurrence order and unused atoms, deduplicates normalized/negated
equivalents, and drops arithmetic atoms that normalize to constants. Empty
vocabulary accepts both constants; missing formula atoms, Boolean constants,
compound declarations, and underlying integer symbols raise `ValueError`.

Both builders use `Mock(spec=PropCompiler)` returning a
`Mock(spec=PropCompiledTarget)`. Assertions check normalized combined formulas,
complete vocabulary, existential versus universal elimination of lemma-only
atoms, pre-registration, and returned artifact, abstraction, projection order,
and environment bindings. A separate reduced example checks preservation and
extension of a supplied sparse abstraction. No shared helpers or fake framework
are added.

Verification: all 19 focused compilation cases (ten ownership and nine new
orchestration cases) and all 1,377 suite cases pass using the main workspace
interpreter. Repository-wide Ruff lint/format, tracked/untracked whitespace
checks, and Pyright over production code and `test_theory_compilation.py` pass
with the established dependency paths. PySMT walker deprecation warnings remain;
the full suite also reports a CUDD shutdown warning about three referenced nodes.
The query-test commit's configured Ruff and Pyright hooks all passed after
temporarily supplying the dependency paths; that local config was removed.

Metrics, compilation lifecycle, compiler-instance validation, real theory
integration workflows, and production fixes remain deferred. These tests check
orchestration; native compiler semantics belong to the compiler contracts.
No production or public API changes were needed.

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
├── __init__.py
├── cases/
│   ├── __init__.py
│   └── formulas.py
├── conftest.py
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
│   │   ├── test_compiler.py
│   │   ├── test_cudd.py
│   │   ├── test_pysdd.py
│   │   └── test_d4.py
│   ├── queries/
│   │   ├── test_engine.py
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
| `test_theory_compiled_target.py` | `TheoryCompiledTarget`: association of target, abstraction, atoms, and environment; delegation of reconstruction/size; save/load of abstraction and atoms. Session creation is deferred to the QuerySession group. Use small fakes where backend semantics are irrelevant.                                                              |
| `test_persistence.py`            | Shared artifact helpers: metadata version checks, malformed or missing metadata, successful atomic save, cleanup after failure, refusal to overwrite an existing destination.                                                                                                            |
| `test_stats_collector.py`        | `StatsCollector`: no-logger execution, dictionary insertion/replacement, controlled-clock conversion and accumulation, timing and exception propagation on failure.                                                                                                                        |
| `test_normalizer.py`             | `NormalizerWalker`: semantic preservation, canonicalization of equivalent supported theory atoms, polarity, idempotence, Boolean structure, explicit environment, close/context-manager behavior. Parametrize by formula family.                                                         |

### Compilers and targets

| File                        | Classes/group and proposed coverage                                                                                                                                                                                                                                                                                                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_compiler.py` | `BddCompiler`, `SddCompiler`, `D4Compiler` and their native targets: Boolean compilation, existential/universal elimination, and compile/save/load preservation of meaning. Further backend coverage remains deferred. |
| `test_cudd.py`              | BDD-specific translation/representation cases, complemented edges, manager ownership, and persistence behavior not covered by shared contracts.                                                                                                                                                                                                      |
| `test_pysdd.py`             | SDD-specific translation/representation cases, variable remapping, vtree/configuration behavior, and native-node ownership.                                                                                                                                                                                                                          |
| `test_d4.py`                | BCS12 translation, d4 output parsing/cleanup and remapping, constant circuits, subprocess failures and missing executable. Mock the process only for process/error handling; use real d4 in semantic contract tests.                                                                                                                                 |

### Query engines and sessions

| File                      | Classes/group and proposed coverage                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_engine.py` | `BddEngine`, `SddEngine`, `DdnnifeEngine`: satisfiability, validity, counting, clause entailment, implicant checking, enumeration, assumptions, and query input validation. Include empty/constant queries, duplicates, contradictory assumptions, tautological clauses, and declared projection dimensions absent from the DAG. Check that sequential queries do not change the target. |
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

Shared compiler and engine contracts use Z3 as an independent oracle; engine
counts and enumeration use Z3 model blocking over the retained vocabulary.
Quantified expectations use `Exists`/`ForAll` formulas. At the propositional compiler/engine layer, theory atoms are
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
