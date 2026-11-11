# Lean refactor execution

[DESIGN.md](DESIGN.md) defines the future contracts. [TODO.md](TODO.md) holds work
outside this sequence. Execute one step per approval cycle; a completed local
check does not authorize the next step.

## Baselines and integration branches

Use `refactor/lean-core` as the integration branch in both repositories. The
branches start at the fetched `main` revisions below, verified on 2026-11-09:

| Repository | Baseline commit |
| --- | --- |
| `masinag/tddnnf` | `937c89ee144ca7edcbd7e7b3225849927633f747` |
| `masinag/tddnnf-testbench` | `6bb66fc06086cd902a32c8bd430942d2a86ec39e` |

`gh` and Codex are installed. GitHub authentication, admin access, and actual
integration-branch pushes were verified for both repositories. Recheck access
when starting a later session; the earlier plan's missing-`gh` prerequisite is
resolved.

The existing testbench checkout at
`/home/gabriele/Documents/theorykc/tddnnf-testbench` has unrelated uncommitted
changes. Preserve it, including its pending migration script. Perform testbench
refactor work in a separate worktree based on its latest integration branch.
Read that worktree's `AGENTS.md`. Do not stage, stash, reset, or copy the pending
changes into a refactor PR.

## Per-step workflow

1. Check prerequisite PRs on GitHub for user approval of their final revisions
   and merge into `refactor/lean-core`. Step 0 has no prerequisite PR. Approval
   without a merge does not unblock dependent work. GitHub is authoritative;
   this file records branches, dependencies, and evidence, not approval state.
2. Fetch `origin`, then create the step branch from the latest
   `origin/refactor/lean-core`. Never commit implementation on the integration
   branch. Preserve unrelated working-tree changes.
3. Implement only the step, including affected callers, tests, fixtures,
   configuration, exports, and documentation. Run the acceptance checks below.
   Record the actual commands, results, versions, and material limits here.
4. Commit the change. For substantive code, pause implementation and obtain a
   fresh read-only review of the committed revision. Address concrete findings,
   rerun affected checks, and commit corrections on the same branch. Step 0
   needs documentation review only, with no extra agent.
5. Push the step branch and open a PR with base **`refactor/lean-core`**. Report
   its link, validation evidence, and limitations, then stop for user approval.
   Do not enable auto-merge, merge without an explicit instruction, or begin
   the next step. Changes after approval require renewed approval.

When a step affects both repositories, create linked companion PRs, each
targeting its own `refactor/lean-core`. Validate them together using their
proposed revisions, and record both SHAs and how the testbench selected that
library checkout. Both PRs must be approved and merged before dependent work.
If an earlier interface change breaks a consumer needed for acceptance, include
its companion PR then rather than postponing it to step 5 or 6.

For example, after prerequisites are merged:

```bash
git fetch origin
git switch -c refactor/01-baseline origin/refactor/lean-core
```

For a testbench companion, choose an unused worktree path (shown as
`/tmp/tddnnf-testbench-01-baseline` here):

```bash
git -C /home/gabriele/Documents/theorykc/tddnnf-testbench fetch origin
git -C /home/gabriele/Documents/theorykc/tddnnf-testbench worktree add \
  -b refactor/01-baseline /tmp/tddnnf-testbench-01-baseline \
  origin/refactor/lean-core
```

Keep development environments and generated benchmark outputs in that isolated
workspace. Check dependency sources explicitly: a relative editable dependency
must resolve to the proposed tddnnf revision, not an unrelated sibling checkout.

After all steps have been approved and merged, open final integration PRs from
`refactor/lean-core` to `main` in each affected repository. Await user approval
and explicit merge instructions again.

## Ordered steps

Each step depends on the preceding step, including all companion PRs. The
acceptance details below extend the table rather than introducing extra stages.

| Step | Branch | Deliverable | Dependency |
| --- | --- | --- | --- |
| 0 | `refactor/00-design` | Design, execution plan, deferred-work list | None |
| 1 | `refactor/01-baseline` | Reproducible test and benchmark baseline | 0 |
| 2 | `refactor/02-compilation` | One pipeline and configured compiler instances | 1 |
| 3 | `refactor/03-target-ownership` | Public backend targets, read-only target bindings, append-only abstraction reuse | 2 |
| 4 | `refactor/04-query-sessions` | Query composition, input handling, native delegation, cleanup | 3 |
| 5 | `refactor/05-persistence` | Versioned persistence and paired consumer migration | 4 |
| 6 | `refactor/06-public-migration` | Public cleanup, examples, full validation | 5 |

### Step 0 — design

Write the three linked documents. Review every agreed decision against the
plan, distinguish future APIs from current behavior, check links and launch
commands, and run `git diff --check`. Confirm the changes contain documentation
only and the testbench working files remain unchanged. Runtime tests and
benchmark runs belong to step 1.

### Step 1 — baseline

Establish the current test environment before implementation. Record the Python,
PySMT/MathSAT, d4 CLI, ddnnife, PySDD, CUDD/dd, and tlemma-enum versions or
revisions and installation commands. Run `uv run pytest` with the project's dev
dependencies available; distinguish environment setup failures from behavioral
failures. Do not reuse historical test counts or timings as new measurements.

Select a fixed representative benchmark subset from the testbench: constants,
ordinary Boolean/theory formulas, both compilation constructions, full and
partial projection, and a small real benchmark sample. Record exact inputs,
commands, seeds, options, machine context, wall time, peak memory, DAG metrics,
artifact size, and existing computation logs. Preserve the baseline revision
and results for the final comparison. Use existing harness commands and helpers.

Reproduce native precision and buffering limitations separately from tddnnf
adapter defects. Give each an installed version, small reproduction, observed
behavior, and impact. Do not add a generic capability framework or compensate
for native counting limits in Python. Include a testbench companion PR if
baseline artifacts or harness changes are needed there.

### Step 2 — compilation

Consolidate T-reduced and T-extended compilation behind one pipeline; accept
configured instances and allocate stable abstraction IDs. Keep external lemma
enumeration, the d4 CLI, existing logging, and native compiler defaults.

Check both constructions across all three compilers, configured options,
constants, empty/default/partial projection, normalized duplicate atoms, and
projection atoms absent from both formula and lemmas. Verify elimination of
non-projection variables, normalized-atom node-ID ordering (reproducible for the
same node creation history in the environment and starting abstraction), IDs
across hash seeds for a fixed creation sequence, environment
validation, subprocess errors, and temporary cleanup. Run affected compiler,
abstraction, normalization, and compilation-context tests. Update broken
testbench callers in a companion PR if needed for these checks.

### Step 3 — target ownership

Keep public backend compiled target classes and bind `TheoryCompiledTarget` to
its environment, abstraction, and immutable active vocabulary. Keep `.target`
as a supported read-only property. Preserve native manager/root lifetimes,
reconstruction, and metrics. Reuse supplied abstractions
with append-only registration and stable IDs; derive SDD counting dimensions
from the native manager so shared growth does not alter earlier targets.

Check targets after compilation-session closure, constants and shared DAGs,
mapping/vocabulary mutation attempts, reconstruction in the bound environment,
and native reordering/minimization without semantic change. Verify resource
cleanup on exceptions and retained root ownership. Run affected target,
compiler, reconstruction, and metrics tests. Backend compiled target classes
and `.target` remain public through step 6.

### Step 4 — query sessions

Add `target.queries(reasoner)` and session-owned normalization, canonical atom
indexing, vocabulary validation, shared query derivations, and projection
bookkeeping. Targets own no normalizers.

Exercise all six queries for each native pairing, with equivalent syntax,
polarity changes, duplicate and contradictory assumptions, malformed and
unknown inputs, constants, empty clauses/cubes, and active atoms absent from
the DAG. Check contradictory satisfiability/count results are `False`/`0`,
native primitive delegation, explicit incompatibility errors, and no implicit
backend substitution. Verify independent sessions, repeated close, exceptions,
temporary-file cleanup, early-stopped enumeration, and target reuse after
session closure. Keep native numerical and buffering limits visible.

### Step 5 — persistence

Implement versioned metadata, codec dispatch, save/load, and legacy migration;
update testbench producers and consumers in linked companion PRs.

Round-trip every representation, constants, nontrivial remapping, inactive and
absent active atoms, custom/minimized SDD vtrees, and reordered OBDDs. Check
environment binding, unknown versions/codecs, corrupt metadata, and missing
declared files. Require the saved vtree for every legacy or versioned SDD
artifact; missing vtrees require recompilation without publishing a destination. Validate safe writes, refusal to
overwrite, and cleanup after failure.

Migration checks cover single, recursive, and dry-run modes; preserved IDs,
projection order, logs, and byte-identical native payloads; DDDMP order recovery;
existing and missing SDD vtrees in legacy and versioned artifacts; and absence of
compilation during migration. Run the
testbench serialization, compile-task, query-consumer, and migration tests
against the proposed library SHA. Record limitations where original structural
metadata cannot be recovered.

### Step 6 — public migration

Migrate exports, examples, README, architecture documentation, and testbench
consumers to the final public interface. Remove obsolete public contexts
and builders after callers have moved. Preserve the public backend compiled
target classes and read-only `.target` property. Simplify
affected tests into small functions and straightforward backend parameterization
while retaining useful helpers and coverage.

Run the complete library suite and affected testbench suite with the proposed
paired revisions. Execute the public examples and compare the fixed step-1
benchmarks, reporting timing, memory, size, and semantic differences. Stable ID
ordering may change native structure and performance; investigate regressions
instead of promising equal timings or byte-identical new compilations. Preserve
existing dependencies, logging, reconstruction, and metrics. Explicit d-DNNF
conversion, transformations, relational queries, extra reasoners, and the Python
d4 compiler stay deferred in [TODO.md](TODO.md).

## Agent setup

Use one implementation agent with write access and reuse its session while the
context remains useful. Pause implementation during a fresh read-only review
of substantive committed changes, especially ownership and persistence. Give
the reviewer the step, relevant design sections, commit range, connected callers,
and test evidence; the entire planning conversation is
unnecessary. Routine documentation and mechanical changes need no extra agent.

| Role | Model | Effort |
| --- | --- | --- |
| Implementation | GPT-6.1 Sol | Medium |
| Difficult mapping | Same implementation agent | High |
| Independent review | GPT-6.1 Sol | High |
| Unresolved semantic/design issue | GPT-6 Astra, bounded task | High |

These are the agreed starting settings. Separate contexts support independent
review; dependent implementation work benefits from retained context. See the
[official subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents).
Subagents inherit the parent sandbox, so use a separately launched read-only
session when an enforced read-only boundary is required.

```bash
# Implementation agent
codex -C /home/gabriele/Documents/theorykc/tddnnf \
  -m gpt-6.1-sol \
  -c 'model_reasoning_effort="medium"' \
  --sandbox workspace-write \
  --ask-for-approval on-request
```

```bash
# Fresh reviewer, launched after the step is committed
codex -C /home/gabriele/Documents/theorykc/tddnnf \
  -m gpt-6.1-sol \
  -c 'model_reasoning_effort="high"' \
  --sandbox read-only \
  --ask-for-approval never
```

For testbench work, replace `-C` with its isolated worktree path. In the app use
equivalent model/effort settings and the prompts below. No custom agent files
or orchestration scripts are needed. The flags were checked against installed
`codex --help`; see also the [CLI reference](https://learn.chatgpt.com/docs/cli/reference).

## Copyable prompts

### Implementation

```text
Implement step <N>: <TITLE> from REFACTOR.md under the contracts in DESIGN.md.

Confirm prerequisite PRs are approved and merged. Create
refactor/<NN>-<slug> from the latest origin/refactor/lean-core.
Preserve unrelated working-tree changes.

Read the affected code and callers. Implement only this step, update its
tests and documentation, and run the documented acceptance checks.
Respect the selected backend's behavior and documented limitations.

Record the completed checks in REFACTOR.md and commit the changes.
For substantive code changes, obtain a fresh read-only review of the
committed diff and address concrete findings before publishing.

Push the step branch and open a PR targeting refactor/lean-core.
Use a concise description of the resulting behavior, validation evidence,
and relevant compatibility risks. If this step affects tddnnf-testbench,
create linked companion PRs targeting its refactor/lean-core branch too.

Return the PR links and check results, then stop.
Do not merge, enable auto-merge, or start another step.
```

### Independent review

```text
Review step <N> on branch <BRANCH>, at commit <SHA>, against
origin/refactor/lean-core and the relevant DESIGN.md/REFACTOR.md contracts.

Read connected callers where needed. Focus on incorrect behavior,
mapping or ownership mistakes, persistence risks, missing focused tests,
and unnecessary abstractions.

Do not request Python replacements or workarounds for accepted native
backend limitations. Distinguish upstream limitations from adapter bugs.

Do not edit files, commit, change branches, or post external comments.
Report actionable findings with file locations and consequences.
If there are none, say so and identify any material verification gap.
```

### Addressing PR feedback

```text
Address my feedback on PR <URL> within its existing step branch.
Keep the agreed scope, update relevant checks, commit the fixes, and
push them to the same PR.

Summarize what changed and return the PR link.
Leave the PR open for renewed approval. Do not merge or start the next step.
```

## Completed checks

Record evidence here as steps are implemented; consult GitHub for approvals and
merges. Steps 0–5 have merged into `refactor/lean-core` and record their checks
below. Step 6 (public migration) is recorded below; explicit d-DNNF conversion is
deferred in [TODO.md](TODO.md#explicit-d-dnnf-conversion). Historical evidence
below retains the step numbers and contracts used at the time.

### Step 0 — `refactor/00-design`

- Compared the existing draft and affected library/testbench interfaces with the
  agreed plan. Replaced conflicting draft decisions and separated deferred work.
- Verified GitHub authentication and push access by creating the two integration
  branches at the baselines above. The testbench working checkout was not switched.
- Checked the documented Codex launch flags with installed `codex --help` and
  consulted the linked official CLI/subagent documentation.
- Documentation review covered every agreed contract, the sequential dependency
  gates, companion PRs, and all three copyable prompts; no separate agent was
  needed for this documentation-only step.
- `git diff --cached --check` passed. The staged file list contains only
  `DESIGN.md`, `REFACTOR.md`, and `TODO.md`.
- A local documentation check passed for all 9 relative links, balanced code
  fences, whitespace, four shell blocks (`bash -n`), and the Python example
  (`ast.parse`). Launch commands were syntax-checked, not used to start agents.
- Compared testbench branch/status and SHA-256 hashes of all 8 pending files
  against the pre-edit snapshot: unchanged. The original untracked design
  draft was backed up outside the repository before editing.
- Runtime tests and benchmarks were not run: this step changes documentation
  only. Step 1 will establish fresh results; no runtime correctness or performance
  claim is made here.

### Step 1 — `refactor/01-baseline`

- Verified design PR [#7](https://github.com/masinag/tddnnf/pull/7) was merged.
  Created the library branch from fetched integration commit
  `df8b22b7ff7adcd7ac795ab27514169ddcee6ecf` and the isolated testbench worktree
  `/tmp/tddnnf-testbench-01-baseline` from
  `6bb66fc06086cd902a32c8bd430942d2a86ec39e`. Existing testbench changes were
  preserved; its branch, pending-file hashes, and status are recorded with the evidence.
- Reused `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv` without
  environment recreation or dependency synchronization. Explicit `PYTHONPATH`
  selects the isolated testbench `scripts`; verified both module paths and the
  editable local library import. Installed only missing MathSAT bindings and d4.
- Versions: Python 3.12.15, PySMT 0.9.7.dev431, MathSAT 5.6.16
  (`412f4b1ef83c`), dd 0.6.0 / CUDD 3.0.0, PySDD 1.0.6, ddnnife 0.10.0,
  tlemma-enum 0.1.0 (`2eff0ae868939c9e885c9fb6ba5d503f8874acb3`), d4
  `dda4511f218dd250e5973d7c27271f7228edc210`. The d4 installer encountered
  CMake 4 policy incompatibility and missing Ninja; only temporary upstream
  build scripts were adapted to Make and policy 3.5. No compiler logic changed.
- Ran `uv run --no-sync python -m pytest -q` in each repository with
  `UV_PROJECT_ENVIRONMENT` pointing to the reused environment and
  `PYTHONHASHSEED=0`: **375 library tests passed** (554 warnings, 11.44 s),
  **182 testbench tests passed** (5 warnings, 4.23 s). The pre-install library
  failures are preserved as environment setup evidence, not behavioral failures.
  CUDD shutdown reference assertions remain visible in the successful suite's warnings.
- The fixed subset covers true/false, Boolean and integer-theory fixtures,
  synthetic `ldd_phi_problems_b10_r10_d4_m20_s1234/02`, and planning
  `h3/block-grouping/instances_simple/block-grouping-simple-2-1`. The testbench
  freezes lemma/query inputs and all hashes. Each runs all three backends,
  `treduced` and `textended-negation`, and `all`/`plans` projection. Extended
  negation retains the existing harness semantics; its answers are not treated
  as answers to the same function as T-reduced compilation.
- The sequential recorder reuses existing compile/query task commands and the
  harness resource guard. It records one warm-up and three measured runs,
  fixed hash seed 0, 60-second task deadlines, and inherited 8 GiB address-space
  limits. Original computation/query logs, wall times, peak RSS, native DAG
  results/errors, artifact bytes/hashes, machine context, and replay commands
  are preserved. GNU Time wraps the task deadline so timed-out tasks retain RSS.
- Native-only reproductions separately show CUDD floating count precision,
  PySDD global-count overflow, ddnnife buffered/u64-bounded enumeration, and
  ddnnife's rejection of zero-feature constant files. The latter is exposed by
  the current DAG adapter; constant queries are handled separately. No native
  limit is repaired or hidden in Python.
- Adapter reproductions show SDD contradictory assumptions returning true/zero,
  and SDD persistence omitting the compiled vtree. A separate native diagnostic
  loads the planning circuit in under a millisecond with its saved vtree;
  a default vtree conflicts with 270 circuit literal positions. These defects
  remain for steps 4 and 5; no production refactoring was performed.
- Full commands, frozen sources, versions, raw records, compact summaries,
  native probes, and one measured artifact per combination are in the
  [testbench baseline evidence](https://github.com/masinag/tddnnf-testbench/blob/refactor/01-baseline/baseline/README.md).
  Source revisions above identify the measured runtime; the paired PR heads add
  documentation and baseline instrumentation/evidence only.
- Stop after publishing the paired PRs. Step 2 requires user approval and merge
  of both baseline PRs.
- Completed **288 records**: 72 warm-ups and 216 measured runs. Across all
  repeats, compilation succeeded 272 times and timed out 16 times. Each query
  type completed 268 times and timed out on 4 SDD planning reloads. DAG checks
  recorded 236 successes, 32 native zero-feature errors, 4 reload timeouts,
  and 16 unavailable results after compilation timeouts. Answers and stage
  outcomes were stable across repeats; failed/censored timings stay explicit.
- Fresh independent read-only Standards/Spec reviews of committed baseline
  instrumentation identified two reporting issues. Both were corrected and
  reviewed again at testbench commit `f571856`: query statuses and observed
  versus completed medians are explicit, and mixed outcomes cannot abort the
  report. Two focused regression checks pass; no review findings remain.
- Verified all frozen input hashes and every archived measured payload against
  recorded hashes, all 288 matrix records, documentation links/shell syntax,
  and unchanged original testbench pending files/status. Production source diffs
  against the measured revisions are empty in both repositories.
- Final testbench validation, including both added regression checks: **184
  passed**, 5 warnings, 3.56 s. The matrix additionally exposes an SDD adapter
  bookkeeping defect: true over an empty active vocabulary counts as 2 instead
  of 1 because the dummy native variable is not removed. This remains documented
  separately from native count overflow.

### Step 2 — `refactor/02-compilation`

- Verified prerequisite library PR [#8](https://github.com/masinag/tddnnf/pull/8)
  and testbench PR [#11](https://github.com/masinag/tddnnf-testbench/pull/11)
  are merged. Created both step branches from freshly fetched integration heads:
  library `baec2264aafd4d1551b2cb71713bf09d6513c82f`, testbench
  `0d64937ee2e14bf490af5fb6c03654dbbe2e0179`. Testbench changes are isolated in
  `/tmp/tddnnf-testbench-02-compilation`.
- Added `TheoryCompilation` (`CompilationContext` remains an alias), a shared
  private compilation pipeline, and forwarding builders. Constructors retain
  backend configuration only; `compile(formula, abstractor, *, project_on=None,
  computation_logger=None)` takes a prepared abstraction and per-call logger.
  Strings and compiler classes are rejected by the compilation session.
- Validate Boolean inputs and every descendant's environment before normalizing;
  normalize/deduplicate positive projection atoms, reject constants and compound
  Boolean projection entries, preserve explicit empty/absent atoms, and allocate
  projection-first IDs followed by SMT-LIB serialization order without aliases.
  Omitted projection comes from normalized phi, excluding lemma-only atoms.
  Extending a caller-supplied sparse abstraction now allocates above its maximum
  ID, avoiding an existing collision that could overwrite a supplied atom.
- `SddCompiler(vtree_type="balanced", auto_gc_and_minimize=True)` explicitly
  constructs a native `Vtree`. The Boolean option jointly controls automatic
  garbage collection and minimization and rejects non-Booleans. Tests inspect
  the native setting for default/True/False under both constructions, use a
  right-linear vtree, and compare semantics. CUDD configuration and d4 CLI,
  projection remapping, diagnostics, temporary cleanup, and log keys remain.
- Compilation/normalizer context managers and idempotent `close()` release owned
  solver resources on exit and partial initialization failure and reject use
  after closure. Query-session lifecycle and target ownership remain deferred.
- Updated tests, public examples, README/architecture, and active testbench
  compilation callers to instances. The testbench closes its normalization and
  compilation sessions even on task failures, retaining CLI modes, result schema,
  logs, and T-extended compilation of `Not(phi)` in `textended-negation` mode.
- Reused the existing testbench `.venv` and editable library, without dependency
  synchronization or installation. Python 3.12.15, PySMT 0.9.7.dev431, PySDD
  1.0.6, dd 0.6.0, ddnnife 0.10.0, and tlemma-enum 0.1.0 match step 1;
  MathSAT and d4 installations are unchanged. Set these variables for the commands:

  ```bash
  export UV_CACHE_DIR=/tmp/uv-cache
  export UV_PROJECT_ENVIRONMENT=/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv
  export PYTHONHASHSEED=0
  ```

- Library: `uv run --no-sync python -m pytest -q` — **522 passed**, 710 warnings,
  13.70 s. The 147 added focused checks cover both constructions/all backends,
  independent Shannon-projected formulas, constants/compound constants,
  omitted/empty/partial/absent projection, normalized duplicates/polarity,
  formula-only and lemma-only elimination, compiler reuse, ID order across hash
  seeds 0/1/99, malformed/foreign DAGs, invalid compilers/options, supplied sparse
  abstractions, closure/initialization failures, and d4 diagnostics/cleanup.
- Testbench, from the isolated worktree with
  `export PYTHONPATH=/tmp/tddnnf-testbench-02-compilation/scripts`:
  `uv run --no-sync python -c 'import tddnnf,tasks.compile; print(tddnnf.__file__,tasks.compile.__file__)'`
  verified the intended library checkout and isolated task module.
  `uv run --no-sync python -m pytest -q` — **184 passed**, 5 warnings, 3.96 s.
- `uv run --no-sync ruff check tddnnf tests examples`, affected-file
  `ruff format --check`, and `git diff --check` pass in the library; testbench
  `ruff check scripts/tasks/compile.py tests/test_compile_task.py` and whitespace
  checks pass. `basedpyright`/`pyright` are not installed in this environment;
  static type checking was not run and dependencies were not changed to add it.
- Ran `uv run --no-sync python examples/abstr.py`, `examples/tred.py`, and
  `examples/text.py`; all complete across the three backends. Raw local test and
  example logs are `/tmp/tddnnf-step2-*.log`.
- Real sample: reused the frozen synthetic `ldd_phi_problems_b10_r10_d4_m20_s1234/02`
  formula, lemmas, and queries. **12 compile tasks and 36 query tasks passed**
  (all three backends, both constructions, all/plans projections, CT/CE/IM).
  Query answers agree across backends within each construction/projection.
  [Companion verification commands](https://github.com/masinag/tddnnf-testbench/blob/refactor/02-compilation/REFACTOR.md)
  reproduce these checks; exact executed argv/stdout/stderr are in
  `/tmp/tddnnf-step2-smoke/commands.json`. This is a semantic smoke check, not
  a repeat of the full timing/memory benchmark matrix.
- Verified original testbench status and SHA-256 hashes of all three pending
  files against `baseline/preserved-checkout.json`: unchanged. Frozen step-1
  evidence, dependencies, artifacts/persistence, and query implementations were
  not migrated. The original native CUDD shutdown assertions/deprecation warnings
  remain visible; documented SDD counting/query/persistence defects and native
  numerical/buffering limits remain for later steps. Stable IDs and native SDD
  settings may change DAG shape, memory, and performance.
- Fresh independent read-only review of library `1e05bdb` and testbench
  `16e0c27` found one SDD configuration defect: an unrecognized vtree name
  terminated the interpreter inside native `Vtree` (exit 1), preventing Python
  cleanup. Constructor validation now rejects unsupported names/types with
  `ValueError`; the five native supported names are verified against installed
  PySDD sources and exercised by tests. Six invalid-input regressions failed
  before the fix and pass afterward. The full library suite above includes
  these corrections. No other review findings were reported.
- Follow-up read-only review at `e2f6ccc` confirmed the finding resolved with no
  new findings, independently running all 11 added vtree checks (**11 passed**).
  The full companion suite was rerun against this correction: **184 passed**,
  5 warnings, 4.03 s. Markdown links/fences and embedded Python/bash syntax pass.
- Paired verified runtime revisions: library
  `e2f6cccff71032ca9cce88904f15dcdb7884da73`, testbench
  `16e0c27776e6494f6445f5a4d6ae4a458cd0c9bd`. Subsequent commits only record
  this review/revision evidence. Both PRs target `refactor/lean-core`; leave them
  open without auto-merge and stop before step 3.

#### PR #9 review updates

- Applied the user's [normalizer review](https://github.com/masinag/tddnnf/pull/9#discussion_r4513168208)
  and [environment-contract clarification](https://github.com/masinag/tddnnf/pull/9#discussion_r4513182122):
  trust annotated FNode inputs and their environment membership. Removed the
  repeated Python/sort checks and the separate whole-DAG ownership traversal;
  `DagWalker` retains its existing memoization. Boolean input and environment
  membership are documented caller preconditions in docstrings and design/API
  documentation. This supersedes the original validation requirements and
  related initial acceptance evidence above.
- Applied the [SDD constructor review](https://github.com/masinag/tddnnf/pull/9#discussion_r4513208347):
  removed Python type checks and documented argument types and the joint native
  Boolean setting. Retained supported-vtree-name validation, since an unknown
  name terminates the native process instead of raising a Python exception.
- Removed both unused `abstr` compiler-fixture arguments per the
  [compiler-test](https://github.com/masinag/tddnnf/pull/9#discussion_r4513272487)
  and [engine-test](https://github.com/masinag/tddnnf/pull/9#discussion_r4513276611)
  comments. Removed 22 obsolete runtime-input-type/environment rejection cases;
  initialization-failure cleanup is still checked using an invalid projection
  value, without violating the annotated input types.
- With the same environment and `uv run --no-sync` commands above, the library
  suite passes **500 tests**, 697 existing native/deprecation warnings, 12.51 s;
  the isolated companion suite passes **184 tests**, 5 warnings, 3.68 s.
  Library lint, affected formatting,
  and whitespace checks pass. No testbench source changes are required.
- Fresh read-only review at `c7053c2` found no actionable issues and independently
  passed all **135** normalization, compilation-context, and pipeline tests.
  Paired feedback-check revisions: library
  `c7053c2cad2415a99c2549195702138b97a64633`, unchanged companion
  `97e8aa5b466c05111fb6c6dce636a61a0dda3b68`. Subsequent library changes only
  record review evidence. Full performance benchmarks and unavailable static
  type checks were not repeated; inputs violating the documented type/environment
  preconditions are intentionally outside the supported contract.

## Remove preliminary testbench normalization

- Compilation now selects `plans` from original formula atoms and includes original
  query atoms before creating one `TheoryCompilation`. Formula/projection counts
  come from that context; lemma/query counts use its normalizer while open.
- The library discards valid projection atoms that normalize to constants,
  including negated atoms. Explicit constants and compound entries remain invalid.
  A code comment explains why constant atoms add no projection dimension.
- Regression checks cover both constructions/all three backends without assigning
  abstraction IDs to discarded atoms; normalized duplicate counts, all CLI modes,
  context cleanup, and original-variable selection after cancellation are covered.
- Using the existing testbench environment and isolated sources: library **516
  tests pass**, testbench **191 tests pass**. Existing MathSAT deprecation and CUDD
  shutdown warnings remain. Affected Ruff lint/format and whitespace checks pass.
- Small synthetic smoke: **12 compilations and 36 CT/CE/IM query tasks pass**;
  query answers agree across backends within each construction/projection.
  Exact commands and logs: `/tmp/tddnnf-no-preliminary-normalization-smoke/commands.json`.
  Original testbench pending files/status still match `baseline/preserved-checkout.json`.
- No timer changes or full performance rerun. `plans` selection intentionally can
  differ when normalization cancels original variables. Both PRs stay open.


## Step 3 evidence — target ownership (2026-11-09)

- GitHub confirms library PR #9 and testbench PR #12 merged. Branch
  `refactor/03-target-ownership` starts at library integration `f54db08`;
  isolated testbench worktree `/tmp/tddnnf-testbench-03-validation` starts at
  integration `f3cd841`. The original testbench checkout was not modified.
- Abstractor copies constructor input and exposes read-only bidirectional views.
  Compilation reuses supplied abstractions with append-only registration in
  stable order, preserving sparse IDs and allocating above the maximum. Targets
  expose read-only bindings to the representation, abstraction, tuple vocabulary,
  and environment. Reconstruction binds to that environment; metrics delegate.
  Public backend compiled target classes and the read-only `.target` property
  remain supported. Artifact formats, native settings, and logs are unchanged.
- PySDD's installed `SddNode.wrap` retains the manager and calls `ref()`; native
  roots/managers remain together without additional manual reference counting.
- Environment: Python 3.12.15, PySMT 0.9.7.dev431, PySDD 1.0.6, dd 0.6.0,
  ddnnife 0.10.0, tlemma-enum 0.1.0, pytest 9.1.1, ruff 0.15.17. Existing
  MathSAT/d4 installations from the baseline were reused; no dependencies changed.
- Commands use `UV_CACHE_DIR=/tmp/uv-cache` and
  `UV_PROJECT_ENVIRONMENT=/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv`.
  `uv run --no-sync python -m pytest -q`: **532 passed**, 729 warnings, 15.60 s.
  Added tests cover session closure + GC, constants/shared DAGs, sparse mappings,
  read-only state/input copies, bound reconstruction under another active
  environment, native minimization/GC and OBDD reordering.
  Existing exception-cleanup tests remain. The loaded-target environment check
  was added afterward and the abstraction suite rerun successfully.
- Testbench suite, from its isolated worktree with
  `PYTHONPATH=/tmp/tddnnf-testbench-03-validation/scripts`, using the same pytest
  command: **191 passed**, 5 warnings, 3.94 s. Before the companion change three
  parameterizations failed on list-versus-tuple equality; its only code change
  updates that assertion. Production consumers require no change.
- All three `uv run --no-sync python examples/{abstr,tred,text}.py` runs pass.
  `uv run --no-sync python /tmp/tddnnf-step3-smoke.py` with the isolated testbench
  PYTHONPATH and `PYTHONHASHSEED=0`: **12 compile + 36 CT/CE/IM tasks passed**,
  with answers agreeing across backends. Inputs are the existing frozen synthetic
  baseline sample; exact argv/stdout/stderr are `/tmp/tddnnf-step3-smoke/commands.json`.
  Other raw logs are `/tmp/tddnnf-step3-*.log`.
- `ruff check tddnnf tests examples`, affected-file `ruff format --check`, and
  `git diff --check` pass. Type checkers remain unavailable; no full performance
  benchmarks, persistence migration, compatibility overloads, or query sessions
  were added. Existing CUDD shutdown-reference/deprecation warnings remain;
  ddnnife zero-feature constant metrics still raise its documented native error
  (covered explicitly), rather than changing metric behavior in this step.

Fresh read-only review of library `148bf20` and companion `3d501dd` reported
**no actionable findings**. Independent focused checks passed **31 tests**, 20
existing warnings (`/tmp/tddnnf-step3-independent-review.log`). Review included
connected ownership, reconstruction, compiler, query, persistence, and metric
code; no implementation corrections were requested. Original testbench pending
file SHA-256 hashes still match `baseline/preserved-checkout.json`.


### Append-only abstraction reuse correction

- Restored `get_id()` registration with the existing `is_atom` assertion. The
  ordinary class owns private dictionaries, copies constructor mappings, and
  exposes read-only live views. New IDs are above the maximum, preserving sparse
  IDs; there is no public deletion or reassignment API. Supplied abstractors are
  extended in deterministic order and shared by compiler and target; absent
  abstractors are created fresh. Backend preparation assertions remain.
- Target bindings remain read-only, projection vocabularies remain tuples, and
  environment ownership is unchanged. SDD forgotten dimensions now use
  `manager.var_count() - len(projection_atoms)`; BDD and d4 counting are unchanged.
- **Reproduced before the SDD fix**, after restoring shared registration:
  an earlier `a OR b` target counted **0 instead of 3** after a second compilation
  added two atoms. Sparse `{7: a}` counted **64 instead of 1**, including under
  assumption `a`; a fresh true constant with empty projection counted **2 instead
  of 1**. The new focused regressions had **7 failures, 11 passes**. Log:
  `/tmp/tddnnf-append-only-before.log`.
- **Current validation**, using the existing testbench virtual environment's
  Python and Ruff directly (no dependency changes):
  `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv/bin/python -m pytest -q`
  passes **552 tests**, 751 existing native/deprecation warnings, 14.78 s.
  The four affected suites pass **245 tests**, 290 warnings, 5.27 s.
  These cover registration, stable sparse IDs, copied inputs, read-only views,
  supplied-object reuse, read-only target bindings, and both builders across all
  three backends. Earlier targets preserve counts, assumptions, enumeration,
  reconstruction, and query scope after growth, with both existing and new
  engines. SDD counts cover sparse IDs, empty projections, and true/false constants.
  Logs: `/tmp/tddnnf-append-only-{focused,full}.log`.
- `ruff check tddnnf tests examples`, affected Python-file `ruff format --check`,
  and `git diff --check` pass. Earlier step-3 testbench **191 passed**, examples,
  smoke **12 compile + 36 query tasks**, and independent review evidence above
  are historical checks, not rerun for this correction. No external testbench
  changes, benchmark reruns, or static type checks were performed.
- Concurrent mutation is unsupported; saved mappings can include atoms from
  later compilations. Existing native shutdown/deprecation warnings and ddnnife
  zero-feature constant metric errors remain. Persistence migration and query
  sessions remain later steps.


### PR #10 review updates

- Applied the [target class review](https://github.com/masinag/tddnnf/pull/10#discussion_r4514843237):
  replaced the frozen dataclass with private fields and getter properties, using
  the same pattern as the backend representations. Public target bindings remain
  read-only; assignment tests now expect `AttributeError`. Tuple projection,
  environment ownership, and append-only abstraction sharing are preserved.
- Applied both [import](https://github.com/masinag/tddnnf/pull/10#discussion_r4514920470)
  [comments](https://github.com/masinag/tddnnf/pull/10#discussion_r4514930806):
  all imports in `tests/test_target_ownership.py` are now top-level, verified
  with an AST check.
- Using the same existing virtual environment, `python -m pytest -q` passes
  **552 tests**, 747 existing native/deprecation warnings, 13.80 s.
  Log: `/tmp/tddnnf-pr10-review-full.log`. Ruff lint across `tddnnf tests examples`,
  affected-file formatting, and `git diff --check` pass. No benchmark, external
  testbench, or static type checks were rerun.


### Public backend target classes (2026-11-10)

- Restored `BddCompiledTarget`, `SddCompiledTarget`, and `D4CompiledTarget` as
  the actual public class names, including compiler annotations, constructors,
  and docstrings. Removed the alias-identity test and its private imports.
  The read-only `.target` property remains supported through the final migration.
- Ownership, getter properties, bound reconstruction, tuple vocabulary,
  append-only abstraction reuse, persistence, and the SDD counting correction
  are preserved. Architecture, design, and step-7 wording now agree.
- Using the existing environment and commands above,
  `uv run --no-sync python -m pytest -q`: **551 passed**, 748 existing
  native/deprecation warnings, 13.71 s. One test was removed from the preceding
  552-test run. Log: `/tmp/tddnnf-public-backend-full.log`.
- `ruff check tddnnf tests examples`, `ruff format --check` on the three compiler
  modules and `tests/test_target_ownership.py`, and `git diff --check` pass.
  Tracked-source searches find no private representation class names or backend
  alias claims. No benchmark reruns, external testbench changes, or static type
  checks; existing native limitations remain.

## Step 4 evidence — query sessions (2026-11-10)

- GitHub confirms prerequisite library PRs #9 and #10 and companion PR #13
  merged. Created `refactor/04-query-sessions` from fetched integration head
  `8ac9df0e2c2536f6f5ef50c7ddeb125354839a01`.
- Added configured `CuddReasoner()`, `SddReasoner()`, and `DdnnifeReasoner()`
  instances and `target.queries(reasoner)`. Sessions share validation,
  normalization/alignment, deduplication, constant handling, and elementary
  derivations. Native validity/conditioning and native d-DNNF counts supply
  reasoning. Each session owns its canonical index, bound normalizer, adapter,
  active iterators, and temporary query files; closure is idempotent and also
  handles exceptions and partial initialization. Targets retain no normalizers.
- Reproduced the integration SDD adapter from `git show
  origin/refactor/lean-core:tddnnf/queries/sdd_engine.py` against a compiled `a`:
  assumptions `[a, Not(a)]` yield satisfiable **True**, count **0**. The new
  session yields **False**, **0**; the legacy SDD adapter also rejects the
  contradiction. Fixed SDD enumeration of sparse IDs and d-DNNF bookkeeping for
  unmapped active dimensions, forgotten dimensions, fixed assumptions, and
  duplicate projected models.
- Retained legacy engines, `QueryContext`, builders, exports, and persistence.
  Examples, README, and architecture now present query sessions. Reused the
  existing exhaustive query/solver tests through sessions on all three native
  pairings, while preserving their legacy engine runs. Added focused tests for
  equivalent syntax/polarity, canonical contradictions, constants, empty scopes,
  full input validation before shortcuts, inactive/unknown atoms, sparse IDs,
  absent active atoms, append-only abstraction growth, native delegation,
  incompatible reasoners, independent sessions, closure, exceptions, failed
  initialization, early-stopped enumeration, and temporary-file cleanup.
- Environment reused without installs or dependency synchronization:
  `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv/bin/python` is
  Python **3.12.15**; PySMT **0.9.7.dev431**, MathSAT **5.6.16**
  (`412f4b1ef83c`), PySDD **1.0.6**, dd **0.6.0** (CUDD **3.0.0**, baseline),
  ddnnife **0.10.0**, tlemma-enum **0.1.0**, pytest **9.1.1**, Ruff **0.15.17**.
  Bundled d4 binary unchanged from the recorded baseline.
- Library command: the above Python with `-m pytest -q`: **775 passed**, 1112
  existing native/deprecation warnings, 23.12 s. Log:
  `/tmp/tddnnf-step4-full.log`. After retaining the original `QueryContext`
  error wording and allowing either session or engine wording in the shared
  validation assertions, `-m pytest -q tests/test_query_sessions.py
  tests/test_bdd_engine.py tests/test_sdd_engine.py tests/test_d4_engine.py`:
  **416 passed**, 674 warnings, 14.05 s. Log:
  `/tmp/tddnnf-step4-acceptance.log`.
- Companion suite from isolated detached checkout
  `/tmp/tddnnf-testbench-04-validation`, integration SHA
  `bd62fcc503c0d63dcd07c5bf4ac7150a71dc1083` (read its `AGENTS.md`):
  **191 passed**, 5 warnings, 3.90 s. Command:
  `PYTHONPATH=/tmp/tddnnf-testbench-04-validation/scripts:/home/gabriele/Documents/theorykc/tddnnf
  UV_CACHE_DIR=/tmp/tddnnf-step4-uv-cache
  UV_PROJECT_ENVIRONMENT=/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv
  uv run --no-sync python -m pytest -q`.
  Verified `tasks.__file__` resolves inside the isolated checkout and
  `tddnnf.__file__` resolves inside this proposed library checkout. Log:
  `/tmp/tddnnf-step4-testbench.log`. The initial run exposed an unnecessary
  change to legacy `QueryContext`'s default environment; restored that default
  while sessions explicitly supply `target.env`. No consumer migration or
  companion PR is needed. Existing testbench working changes remain untouched.
- The same Python ran `examples/abstr.py`, `examples/tred.py`, and
  `examples/text.py` successfully across all backends. Logs:
  `/tmp/tddnnf-step4-example-{abstr,tred,text}.log`. T-reduced counts are **3**;
  T-extended implicant checks are **True** for each backend.
- `ruff check tddnnf tests examples`, `ruff format --check` on all 11 affected
  Python files, documentation Python-block syntax/local links/fences, and
  `git diff --check` pass. No new dependencies, benchmarks, persistence changes,
  native numerical workarounds, or external testbench migration. No static
  type check was run. CUDD floating-point counting, PySDD global-count overflow,
  ddnnife buffered/u64-limited enumeration, and existing native shutdown warnings
  remain; derived d-DNNF answers inherit native counting limits.
- Fresh committed-revision read-only review and delivery evidence follow below.


### Step 4 independent review and corrections

- Committed implementation `e26d4d9` and formatting correction `51f4c61`.
  Paused implementation and launched a fresh reviewer with:
  `codex exec --ephemeral -C /home/gabriele/Documents/theorykc/tddnnf
  -m gpt-6.1-sol -c 'model_reasoning_effort="high"'
  -c 'approval_policy="never"' --sandbox read-only
  --output-last-message /tmp/tddnnf-step4-review.md`.
  The review inspected `8ac9df0...51f4c61`, the contracts and connected callers;
  it changed no files or branches and posted no external comments. Full log:
  `/tmp/tddnnf-step4-review.log`. Independently verified **148 CUDD/SDD tests**
  and **81 native ddnnife bookkeeping assertions**, bypassing file creation
  for the read-only sandbox; the reviewer did not rerun full suites or file
  cleanup tests.
- Addressed both P2 findings. Stored theory atoms that normalize to constants
  now retain exact atom/polarity alignment for sessions and legacy wrappers;
  explicit Boolean constants retain ordinary Boolean semantics. Legacy formula
  alignment substitutes aligned atoms before they can collapse to constants.
  Added true/false-normalizing stored-atom regressions across all three pairings.
  Legacy d4 satisfiability now checks contradictory assumptions before dropping
  unmapped literals; added that regression to the unmapped-dimension fixture.
- After corrections, the existing environment's Python command
  `-m pytest -q tests/test_query_sessions.py tests/test_normalizing_queries.py
  tests/test_d4_engine.py` passes **298 tests**, 476 warnings, 9.58 s. Log:
  `/tmp/tddnnf-step4-review-fixes.log`.
- Final full library rerun: **781 passed**, 1120 existing native/deprecation
  warnings, 23.16 s (`/tmp/tddnnf-step4-final-full.log`). Final full companion
  rerun with the same isolated checkout, SHA, and environment command above:
  **191 passed**, 5 warnings, 3.92 s
  (`/tmp/tddnnf-step4-final-testbench.log`). All three examples were rerun and
  pass; Ruff lint, all 11 affected Python-file formatting checks, and
  `git diff --check` also pass. No benchmark or static type checks were run.
  The documented native limitations remain. No step-5 work was performed.
- Delivery: pushed implementation and review corrections through `6606a6a` on
  `refactor/04-query-sessions`; opened
  [PR #11](https://github.com/masinag/tddnnf/pull/11) targeting
  `refactor/lean-core`. Left open for user review, without auto-merge or step-5
  work. This final entry only records delivery.

### Step 4 projection invariant correction (2026-11-10)

- Supersedes the stored-constant compatibility behavior in the independent
  review corrections above: projection construction already discards atoms
  that normalize to Boolean constants. `QueryContext._index_atoms()` now
  asserts this invariant with `Projection atoms must not normalize to constants`.
  Manually constructed targets that violate it raise `AssertionError` during
  query-context/session initialization, and the normalizer is closed on failure.
- `_align_literal()` handles any canonical Boolean constant directly; its
  target-index compatibility branch is removed. Normalization polarity handling
  remains because valid theory atoms can normalize to negated atoms.
- Replaced stored-constant compatibility tests with true/false-normalizing
  invalid-vocabulary tests for direct contexts and sessions on all three native
  pairings, including index clearing and normalizer cleanup. Retained existing
  polarity/session query-constant regressions and added direct-context checks
  for explicit and normalized constants, including negation and formula alignment.
- Verification using the existing testbench environment (no installs): library
  `python -m pytest -q` passes **789 tests**, 1128 existing native/deprecation
  warnings, 25.80 s (`/tmp/tddnnf-projection-invariant-final-library.log`).
  The same isolated companion checkout and explicit library `PYTHONPATH` recorded
  above pass **191 tests**, 5 warnings, 4.06 s
  (`/tmp/tddnnf-projection-invariant-companion.log`); verified both import paths.
  All three examples pass (`/tmp/tddnnf-projection-invariant-example-*.log`).
  `ruff check tddnnf tests examples`, formatting checks for the three changed
  Python files, and `git diff --check` pass. No benchmark or static type checks
  were run; existing native limitations remain. This correction updates PR #11
  on `refactor/04-query-sessions` and leaves it open for review.

### Step 4 review response — merged query sessions (2026-11-10)

- Supersedes the previous context/Reasoner API: `target.queries(BddEngine)` returns
  `QuerySession[BddCompiledTarget]`. Sessions now directly own their normalizer,
  canonical index, validation, engine, and generator cleanup. Removed QueryContext,
  NormalizingQueryEngine, empty Reasoner classes, and the pairing registry.
- Engines check compatibility and implement all backend-specific reasoning.
  Restored whole-literal polarity normalization; absorbing constants return before
  deduplication, after every input is validated. Imports are top-level, with
  annotation-only dependencies under TYPE_CHECKING.
- Nonconstant D4 engines assert exact projection mapping to dense native IDs.
  Absent DAG atoms remain mapped. Removed partial-mapping count correction and
  forgotten-dimension enumeration deduplication; invalid manual artifacts fail.
- Tracked ordinary generators replace the iterator wrapper. Session closure
  exhausts generators (StopIteration), while closed query methods raise
  RuntimeError. ExitStack preserves cleanup when another cleanup raises.
- Companion worktree `/tmp/tddnnf-testbench-04-sessions`, branch
  `refactor/04-query-sessions`, starts at integration `bd62fcc`. The query task
  loads one session per batch and closes it on success/failure. Existing main
  checkout modifications are untouched. No persistence, schema, or CLI migration.
- Existing environment Python `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv/bin/python`
  ran `-m pytest -q`: **784 passed**, 1121 native/deprecation/shutdown warnings,
  24.18 s (`/tmp/merged-final-library.log`). Companion suite: **191 passed**,
  5 warnings, 4.20 s (`/tmp/merged-companion.log`), using explicit
  `PYTHONPATH=/tmp/tddnnf-testbench-04-sessions/scripts:/home/gabriele/Documents/theorykc/tddnnf`.
  All three examples passed (`/tmp/merged-example-*.log`).
- Ruff lint, changed-file formatting and whitespace checks pass in both repos.
  Focused basedpyright checks pass for session/container and a valid inference
  snippet, with explicit dependency search paths in `/tmp/merged-pyright.json`;
  a mismatched D4Engine/BDD snippet produces the expected argument-type error.
  No full-project type check or benchmarks. Native limitations remain.
- Committed-revision review and linked delivery follow; both PRs stay open.

### Merged-session committed review and delivery

- Fresh ephemeral read-only review inspected library `491de46639c03de619bd8fc7734be4a19949c13d`
  and companion `1d91cac0090b3f50a8ae605d441fac22c937af55`. Report:
  `/tmp/merged-review.md`; full log `/tmp/merged-review.log`. Reviewer passed
  285 tests and 480 native D4 assertions using existing files; its sandbox could
  not run file-creating tests. Full file-based validation was run separately.
- One P2 finding: closing an unstarted generator retained it in the session's
  tracking set. Corrected by registering only when iteration starts; unstarted
  generators advanced after session closure immediately stop. A regression
  creates/closes 1,000 unstarted generators per backend and checks no retention.
- Native saved targets were also loaded through the migrated companion caller
  for all three backends: equivalent-atom counts, entailment, implicant checks,
  and normalizer closure passed. Verified import paths select both proposed
  checkouts. Main testbench changes remain untouched.
- Updated [library PR #11](https://github.com/masinag/tddnnf/pull/11) and opened
  [companion PR #14](https://github.com/masinag/tddnnf-testbench/pull/14), both
  targeting their own `refactor/lean-core`. Both remain open; no merge or step-5
  work. This entry supersedes the previous no-companion-needed delivery notes.
- After review correction: full library **787 passed**, 1121 warnings, 26.33 s
  (`/tmp/merged-reviewed-library.log`); full companion **191 passed**, 5 warnings,
  4.15 s (`/tmp/merged-reviewed-companion.log`). Focused type/inference checks,
  formatting and whitespace checks pass again. No benchmarks or full-project
  static analysis; existing native limitations remain.


### Engine backend naming correction (2026-11-10)

- Renamed `D4Engine` to `DdnnifeEngine` and `d4_engine.py` to
  `ddnnife_engine.py`, matching the query backend. Updated exports, imports,
  error wording, temporary-directory prefix, test module/class, examples,
  README, architecture, and the companion backend table. The old class/module
  have no compatibility aliases: callers must update their imports.
- `D4Compiler`, `D4CompiledTarget`, and the companion `"ddnnf"` backend identifier
  remain unchanged. Earlier evidence above and frozen baseline logs preserve
  their historical names.
- Existing environment Python
  `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv/bin/python`
  ran `-m pytest -q`: **787 passed**, 1121 existing warnings, 23.79 s
  (`/tmp/ddnnife-rename-library.log`). Companion **191 passed**, 5 warnings,
  3.89 s (`/tmp/ddnnife-rename-companion.log`), from
  `/tmp/tddnnf-testbench-04-sessions` with
  `PYTHONPATH=/tmp/tddnnf-testbench-04-sessions/scripts:/home/gabriele/Documents/theorykc/tddnnf`,
  `UV_CACHE_DIR=/tmp/uv-cache`, and the existing `UV_PROJECT_ENVIRONMENT`, using
  `uv run --no-sync python -m pytest -q`.
- All three examples pass (`/tmp/ddnnife-rename-example-{abstr,tred,text}.log`).
  Library Ruff lint, companion changed-file lint, changed-file formatting, and
  both whitespace checks pass. Focused basedpyright checks pass using
  `/tmp/merged-pyright.json` for session/container and `/tmp/merged-typing.py`
  for BDD and Ddnnife generic inference. `/tmp/merged-typing-invalid.py` produces
  exactly the expected engine/target argument-type error.
- Searches find no old class/module references in executable code or current
  documentation in either checkout; historical evidence is retained. No new
  behavioral tests, benchmarks, full-project type checks, or unrelated cleanup.
  Native limitations remain. Updates ship on the existing query-session branches
  and PRs [#11](https://github.com/masinag/tddnnf/pull/11) and
  [#14](https://github.com/masinag/tddnnf-testbench/pull/14), left open.

### Clean d4 compilation output and native total enumeration (2026-11-10)

- New `D4Compiler.compile()` results retain only signed edge literals with IDs
  in `1..len(projected_ids)`, preserving nodes, edge endpoints, terminating zeros,
  and edges that become literal-free. The supported d4 circuit parser assigns
  sorted `P` variables first: raw NNF IDs already match the existing dense
  abstraction remapping and are not renumbered. This cleanup relies on d4's
  projection contract; it is not general existential projection of arbitrary
  d-DNNFs. Constant and empty-projection paths are unchanged.
- Metadata still maps every projected dimension, including dimensions absent
  from the DAG. `DdnnifeEngine` maps total native assignments directly into
  dictionaries in `projection_atoms` order, removing unmapped-literal filtering
  and Python missing-dimension expansion. Constant enumeration, zero-count
  handling, exact mapping assertions, and resource cleanup remain.
- Parameterized compiler regression exercises real d4 and injected output with
  positive/negative leftover literals, ID gaps, and an emptied edge. Sparse
  abstraction IDs and reordered projection atoms verify reconstruction, unique
  total enumeration, counts and assumptions before/after save/load. Python
  expansion is disabled in this regression, proving absent dimensions come
  from ddnnife. Loading a legacy artifact preserves its original text; only new
  compilations are cleaned. Persistence formats and public APIs are unchanged.
- Existing testbench environment Python
  `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv/bin/python`
  ran `-m pytest -q`: **789 passed**, 1124 existing native/deprecation warnings,
  31.47 s (`/tmp/d4-clean-library.log`). Focused compiler/engine/session tests:
  **354 passed**, 554 warnings (`/tmp/d4-clean-focused.log`).
- Companion checkout `/tmp/tddnnf-testbench-04-sessions` ran
  `uv run --no-sync python -m pytest -q` with the existing environment,
  `UV_CACHE_DIR=/tmp/uv-cache`, and explicit
  `PYTHONPATH=/tmp/tddnnf-testbench-04-sessions/scripts:/home/gabriele/Documents/theorykc/tddnnf`:
  **191 passed**, 5 warnings, 5.38 s (`/tmp/d4-clean-companion.log`). Verified
  library and companion import paths; no companion source changes were needed.
- All three examples pass (`/tmp/d4-clean-example-{abstr,tred,text}.log`).
  `.venv/bin/ruff check tddnnf tests examples`, changed-file formatting and
  `git diff --check` pass. Focused session/container and generic inference checks
  pass with `/tmp/merged-pyright.json` and `/tmp/merged-typing.py`; the invalid
  pairing in `/tmp/merged-typing-invalid.py` produces exactly the expected
  argument-type error. No benchmarks, full-project type analysis, or unrelated
  cleanup; existing native counting and enumeration limits remain.
- Delivered on `refactor/04-query-sessions` through library PR #11; companion
  PR #14 records the matching verification. Both remain open.

### Step 5 — persistence implementation and independent review (2026-11-11)

- Branch `refactor/05-persistence` starts at the fetched integration head
  `fc8a541` (companion: `f5d3c48`). Implementation uses isolated worktrees
  `/tmp/tddnnf-05-persistence` and `/tmp/tddnnf-testbench-05-persistence`.
  The original testbench's modified `pyproject.toml`, `uv.lock`, and untracked
  `scripts/migrate_compiled_metadata.py` are untouched.
- Shared version 1 codecs handle standalone and container saves. Metadata
  dispatches representation/codec and declares files, counts, dense d4 remapping,
  complete OBDD order, and the actual SDD vtree. Save validation occurs in a
  temporary sibling before publication; existing destinations are refused.
- Loading validates IDs, ordered projection, active support, mapping coverage,
  native record structure, and declared files. It binds the selected PySMT
  environment. Legacy artifacts require migration. Explicit missing-original-vtree
  exceptions retain their provenance through load/save and cannot certify an SDD.
- The companion adds only the standalone `scripts/migrate_compiled_targets.py`,
  with single/recursive/dry-run execution, unchanged native/log/auxiliary bytes,
  DDDMP order recovery, projection aliases/conflict rejection, isolated validation,
  continuing per-artifact errors, and separate artifact/timing CSV flags.
  Compile/query/plot consumers use inferred loading, and compilation no longer
  creates the artifact destination prematurely. The query helper now flattens
  literals for the existing flat-list API.
- Verification: library **953 passed**, 1159 existing warnings, 27.74 s;
  companion **219 passed**, 5 warnings, 12.89 s. Commands used `uv run --no-sync
  python -m pytest -q --disable-warnings`, `UV_CACHE_DIR=/tmp/uv-step05-cache`,
  explicit paired source `PYTHONPATH`, and existing library/testbench environments.
  The library worktree uses a copy of the existing ignored d4 binary; no binary
  or dependency lock was changed. Library Ruff (`tddnnf tests examples`), companion
  Ruff (`scripts tests`), formatting checks, and `git diff --check` pass.
- Independent agent review found native reader crash cases, incomplete d4 mapping
  coverage, lost missing-vtree provenance on resave, and output-error classification
  issues. All were fixed with regressions. DDDMP IDs/ranks/permutations and native
  ASCII records are checked before C import. SDD roots are rebuilt using public
  operations after disjoint/exhaustive/compressed partition validation, avoiding
  the unsafe raw reader. Migration native validation runs in a subprocess so a
  native failure leaves a report row and processing continues. Source health is
  checked separately from destination I/O failures; report output opens before
  publication and each row is flushed to disk. Final independent review reported
  **no outstanding findings**, independently passing 78 persistence and 28 migration
  tests. Native probes were targeted, not exhaustive.
- Original missing SDD vtrees cannot be recovered. Historical timing logs remain
  unchanged; every processed historical result requires a fresh timed compilation.
  Format migration alone does not require recompilation when all data validates.
  No benchmark compilation/query reruns were performed for this step.


### Step 5 simplification — trusted native payloads (2026-11-11)

- Replaces the native-validation design recorded above. Container persistence
  delegates to backend classes; those classes use CUDD/PySDD directly or preserve
  d4 NNF text. `persistence.py` now contains only metadata/filesystem helpers.
  Handwritten DDDMP/SDD/vtree/d4 graph validation, packed graph arrays, custom
  SDD reconstruction, central native dispatch, and save-time native reloads are
  removed. Runtime imports are module-level; type-only imports use `TYPE_CHECKING`.
- Retains versioned metadata, full OBDD order, actual SDD vtrees, d4 remapping,
  abstraction IDs, ordered projection, environment binding, overwrite refusal,
  temporary cleanup, and explicit missing-vtree provenance. Metadata and mapping
  checks remain; native support and graph correctness are no longer certified.
- Migration calls the public container/backend loaders in its subprocess and
  keeps only DDDMP header extraction for historical order. Native-reader failures
  remain per-artifact report failures. The existing recompilation CSV remains
  historical evidence from the previous validation boundary; no dataset scan or
  benchmark was repeated.
- Malformed native files may crash ordinary loading. d4 loading only preserves
  text; it does not prove graph validity. Migration subprocesses contain native
  reader failures, but successful loading does not certify circuit semantics.
- Verification with the existing testbench environment's Python and explicit
  paired-source `PYTHONPATH`: library `python -m pytest -q --disable-warnings`
  **948 passed**, 1151 existing warnings, 25.46 s; companion **230 passed**,
  5 existing warnings. Ruff passes for both complete source/test trees. Library
  formatting passes across all 47 files; changed companion files pass formatting.
  The companion-wide formatting check still flags four unchanged files:
  `scripts/plots/plot_query_time.py`, `scripts/tasks/generate_synthetic_queries.py`,
  `tests/test_plot_query_time.py`, and `tests/test_query_mathsat.py`.
- Fresh-process import smoke checks pass for container, helpers, backends,
  queries, installer, and migration. An AST check confirms no function-local
  runtime imports in `tddnnf`; paired source paths are verified. Both
  `git diff --check` checks pass, and the historical CSV is byte-identical to HEAD.
  No native malformed-file probes, dataset scans, benchmarks, or unrelated
  formatting changes were performed.


### Step 5 follow-up — convention-based persistence (2026-11-11)

- Supersedes the metadata and mapping checks retained in the previous entry.
  Package-created artifacts are trusted state. Removed `_read_data`, abstraction
  reconstruction during save, custom JSON parsing, manifest/codec checks, backend
  mapping/order validators, and ID/projection cross-checks. Only the schema-version
  gate remains; missing data and backend errors propagate naturally.
- APIs and version 1 artifact layout are unchanged. Full OBDD order, actual SDD
  vtrees, d4 mappings, sparse abstraction IDs, ordered projection, environment
  binding, overwrite refusal, temporary cleanup, and explicit legacy missing-vtree
  provenance remain. Malformed or manually edited artifacts may load incorrectly,
  raise ordinary exceptions, or crash native readers.
- Migration keeps historical recovery checks, byte copying, reports, and public
  loading in subprocesses. Its local JSON reader rejects non-object historical
  JSON so metadata, abstraction, or log failures cannot stop recursive reporting.
  Nine regression cases cover these failures and continuation to the next artifact.
- Verification uses `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv/bin/python`
  with `PYTHONPATH=/tmp/tddnnf-05-persistence:/tmp/tddnnf-testbench-05-persistence/scripts`.
  In each worktree, `python -m pytest -q --disable-warnings` passes: library
  **905 passed**, 1159 warnings, 30.02 s; testbench **239 passed**, 5 warnings,
  17.53 s. Removed tests asserted defensive guarantees deliberately dropped here.
- `ruff check tddnnf tests` and `ruff check scripts tests` pass. Library
  `ruff format --check tddnnf tests` passes (44 files); changed migration/test
  formatting passes. Full companion formatting flags the same four unchanged
  files recorded above. Fresh-process imports verify both proposed source paths;
  both `git diff --check` checks pass. Historical CSV is unchanged from HEAD.
- Skipped dataset scans, benchmarks, malformed native-file probes, and unrelated
  cleanup. No historical CSV regeneration or compilation/query reruns.


### Save workflow naming (2026-11-11)

- Renamed the internal `publication` helper to `saving_to` and its `stage`
  variables to `temporary_directory` across backend/container saves and paired
  migration/tests. The helper documents temporary writes, rename on success,
  and cleanup on failure. Backend `mkdir()` calls and container delegation remain;
  public APIs, version 1 artifacts, overwrite refusal, and cleanup are unchanged.
- Both suites ran with
  `PYTHONPATH=/tmp/tddnnf-05-persistence:/tmp/tddnnf-testbench-05-persistence/scripts`
  and the existing testbench environment. Library: its `.venv/bin/python -m pytest
  -q --disable-warnings`, **905 passed**, 1156 warnings, 27.44 s. Companion:
  `uv run --no-sync python -m pytest -q --disable-warnings` with the existing
  `UV_PROJECT_ENVIRONMENT` and `/tmp/uv-step05-cache`, **239 passed**, 5 warnings,
  15.47 s. Logs: `/tmp/saving-to-{library,testbench}.log`.
- Ruff passes for library `tddnnf tests examples` and companion `scripts tests`;
  formatting passes for all seven changed Python files. Both `git diff --check`
  checks pass. No new tests, abstractions, benchmarks, or dataset scans for this
  naming-only change. Deliver together through library PR #12 and companion PR #15.


### Require saved SDD vtrees (2026-11-11)

- Supersedes the missing-vtree fallback and provenance behavior recorded in earlier
  step 5 evidence. Every SDD save writes and declares `circuit.vtree`; loads restore
  the saved tree before reading the SDD. Public APIs and schema version 1 remain.
- Migration requires the vtree for legacy and versioned SDD artifacts. Missing trees
  fail with `missing_required_data`, require recompilation, and publish no destination.
  Removed the missing-vtree return value, special reason code, and fallback diagnostics.
  Subprocess isolation, recursive continuation, dry runs, overwrite refusal, and cleanup remain.
- Full paired-source verification: library **907 passed** (1155 warnings, 25.52 s),
  testbench **245 passed** (5 warnings, 15.72 s). Used the existing library/testbench
  virtualenvs with explicit `PYTHONPATH=/tmp/tddnnf-05-persistence` and the companion
  `scripts` directory for testbench tests. Ruff passes for library `tddnnf tests examples`
  and companion `scripts tests`; formatting passes for all five changed Python files;
  both `git diff --check` checks pass. Import checks confirm the paired worktree sources.
- Historical evidence and CSV files are unchanged. Recompilation jobs, dataset scans,
  benchmarks, and historical report regeneration were skipped. Previously migrated SDD
  artifacts without vtrees are unsupported and require recompilation.


### Node-ID atom ordering

- Branch `perf/node-id-atom-order` starts at integration revision `9dc7cfe`.
  Both `TheoryCompilation` sorts now use normalized atoms’ `FNode.node_id()`;
  explicit projection order, normalization/deduplication, supplied abstraction
  IDs, sequential append-only allocation, public signatures, and persistence
  formats are unchanged. Creation history in the environment determines order;
  node IDs are sorting keys, never abstraction IDs. Historical evidence above
  records the former serialization-order contract and remains unchanged.
- Regression coverage uses nonalphabetical Boolean creation order and theory
  atoms whose canonical node creation order differs from their raw nodes.
  It covers default and explicit projection, remaining-atom allocation, both
  constructions, all three backends, and sparse abstraction reuse without
  renumbering. The existing subprocess test retains three hash seeds and all
  backends for a fixed creation sequence. Running the 30 new/extended cases
  against the integration revision’s in-memory pipeline gives **30 failed**;
  the changed pipeline suite gives **165 passed**, 183 warnings, 3.08 s.
- Environment: existing `.venv`, Python **3.12.15**, PySMT **0.9.7.dev431**,
  dd **0.6.0**, PySDD **1.0.6**, ddnnife **0.10.0**, tlemma-enum **0.1.0**,
  pytest **9.0.3**, Ruff **0.15.17**; Linux x86_64. No dependency changes.
- `.venv/bin/python -m pytest -q --disable-warnings`: **953 passed**, 1187
  native/deprecation warnings, **23.72 s** (`/tmp/node-id-full-suite.log`).
  `.venv/bin/python examples/abstr.py`, `examples/tred.py`, and
  `examples/text.py` all exit successfully across their backend loops (logs
  `/tmp/node-id-example-{abstr,tred,text}.log`). Ruff lint for `tddnnf tests
  examples`, changed Python-file formatting, relative documentation links, and
  `git diff --check` pass. The link check also found a pre-existing README DOI
  link missing `https://`; its URL is corrected.
- Temporary benchmark `/tmp/node-id-sort-benchmark.py` constructs 1,000 distinct
  normalized linear real arithmetic atoms over 20 variables, with inequalities
  `x[i % 20] + (i % 13 + 1) * x[(i + 1) % 20] <= i + 1` for `i=0..999`.
  Both keys sort the same atom tuple: `to_smtlib(atom, daggify=False)` versus
  `FNode.node_id`. Seven repeats of 30 sorts give median **23.4613 ms/sort**
  for serialization and **0.03461 ms/sort** for node IDs (minimum **23.2792**
  and **0.03189 ms/sort**). Run with `PYTHONPATH=. .venv/bin/python
  /tmp/node-id-sort-benchmark.py`; results are in
  `/tmp/node-id-sort-benchmark.json`. These are sorting timings only; no total
  compilation speedup is established.
- No testbench changes, full benchmark campaign, or static type checks. Native
  variable order, circuit size, and total compilation time may change; ordering
  is not canonical across different node creation histories. Existing saved
  artifacts retain their recorded abstraction IDs.


### Step 6 — public migration (2026-11-11)

- Isolated branches `refactor/06-public-migration` start at library `0314647`
  and testbench `e431af3` in `/tmp/tddnnf-06-public-migration` and
  `/tmp/tddnnf-testbench-06-public-migration`. GitHub confirms prerequisite
  PRs #15/#17 merged at 13:58:45/14:00:33 UTC. Original checkouts, including
  the testbench’s unrelated pending files, are untouched.
- Public exports are `TheoryCompilation` and `TheoryCompiledTarget`. Both
  compilation methods forward keyword-only `abstractor=None` to the existing
  pipeline, preserving positional logger arguments, IDs, projection order,
  and append-only reuse. Removed builders and the `CompilationContext` alias
  after migrating callers. Compiler modules, backend targets, `.target`, and
  engine-class query sessions remain public. No module rename or reasoner layer.
- Compiler/engine/session matrices now use functions and parameterized fixtures;
  their solver comparisons and native regressions remain. The common engine
  fixture closes all successfully opened engines/sessions after each test.
  Documentation describes replacements and supplied-abstraction reuse.
- Paired source selection for all suites and the benchmark is explicit:
  `PYTHONPATH=/tmp/tddnnf-06-public-migration:/tmp/tddnnf-testbench-06-public-migration/scripts`.
  Existing environments are reused without sync or dependency changes. Library
  interpreter: `/home/gabriele/Documents/theorykc/tddnnf/.venv/bin/python`;
  companion interpreter: `/home/gabriele/Documents/theorykc/tddnnf-testbench/.venv/bin/python`.
  The existing ignored d4 binary was copied into the library worktree.
- Commands: library `python -m pytest -q --disable-warnings`: **954 passed**,
  1187 warnings, 29.96 s. Companion `python -m pytest -q --disable-warnings
  tests baseline/test_recorder.py baseline/test_summary.py`: **195 passed**,
  5 warnings, 4.43 s. Focused pipeline: **166 passed**. All three
  `python examples/{abstr,tred,text}.py` invocations exit successfully.
  Raw logs are `/tmp/step06-{library,testbench,focused,recorder,example-*}.log`.
- Recorder resource files now live in a sibling `compile/` directory so the
  target destination stays absent until save. Its regression invokes the real
  recorder entry point and compiler on an absent destination. Both recorder
  and summarizer accept `--results-dir` and `--evidence-dir`; summary tests
  cover defaults and custom paths without creating baseline output.
- Fixed campaign command (from companion worktree, with paired `PYTHONPATH`
  and `PYTHONHASHSEED=0`): `python baseline/run.py --results-dir results_step06
  --evidence-dir validation/step06`. Six frozen cases, three backends, two
  constructions, two projections, one warm-up and three measured runs remain;
  per-task deadline 60 s, 8 GiB address-space limit. Then `python
  baseline/summarize.py --results-dir results_step06 --evidence-dir validation/step06`.
- Paired validated runtime revisions: library
  `ddf8e5479786eb755de98f34487f25b07aa1b9a0`, companion
  `4f9ac8f54444c8012900ad4feb124aa6f15599f8`. Subsequent commits contain
  evidence/docs only. The campaign began before recorder formatting and the
  consumer import-path change; measured repeats use the final sources, and
  neither adjustment changes behavior. Environment/source hashes and all
  records are preserved in the companion `validation/step06/` directory.
- Environment: Python **3.12.15**, PySMT **0.9.7.dev431**, MathSAT **5.6.16**
  (`412f4b1ef83c`), dd **0.6.0** / CUDD **3.0.0**, PySDD **1.0.6**,
  ddnnife **0.10.0**, tlemma-enum **0.1.0**, Ruff **0.15.17**.
  Library pytest is **9.0.3**, companion pytest **9.1.1**. The d4 binary hash
  matches step 1 (`23353293da4575054734195f24c28e3b522686d4e34dc02194295ffdd470fc49`),
  built from `dda4511f218dd250e5973d7c27271f7228edc210`.
- Fixed matrix: **288 records**, 72 warm-up and 216 measured; **280 successful
  compilations, 8 timeouts** versus 272/16 in step 1. All eight timeouts are
  d4 extended planning (both projections, all repeats). Each query type and DAG
  measurement has **248 successes and 32 native zero-feature errors**; DAGs are
  unavailable after the eight compile timeouts. No query-load timeouts remain.
  Answers and stage statuses are stable across repeats.
- Four mutually available answers change: SDD empty-vocabulary true counts
  **2 → 1**. Other available answers match step 1. The 42 availability changes
  separately record d4 constants now exposing native errors (behavior established
  before step 6), successful SDD planning full-projection loads with saved vtrees
  (31,329 unconditional / 25,992 conditioned, matching BDD/d4), and newly completed
  SDD extended planning cells. No unavailable result is treated as zero.
- Median per-cell compile-time / peak-RSS / artifact-byte ratios over matched
  successful cells: OBDD **1.013 / 0.975 / 1.402**, SDD **1.009 / 0.977 / 1.815**,
  d-DNNF **0.992 / 0.982 / 1.454**. Versioned metadata/mappings and SDD vtrees add
  bytes, particularly to small artifacts. Full per-cell timing, memory, artifact,
  DAG, answer and status comparison is in `summary.csv` and `comparison.json`.
- Investigated full-planning BDD slowdown: reduced **3.433 → 4.572 s**,
  extended **3.368 → 4.601 s**. Reduced artifacts shrink **132,013 → 92,187 bytes**,
  vertices **5,696 → 3,571**, edges **11,390 → 7,144**; peak RSS falls
  **111,008 → 90,772 KiB**. All 135 atom IDs differ after canonical alignment
  with step 1, affecting native ordering/construction. `_compile` AST and core,
  compiler and engine sources are unchanged from prerequisite `0314647`.
- Alternating prerequisite/step-6 control, after the campaign, uses `git archive
  0314647 tddnnf` under `/tmp/tddnnf-06-control`, the same frozen planning inputs,
  two full-projection BDD constructions and warm-up plus three measured repeats.
  Command: paired environment `python /tmp/step06-control.py`. Prerequisite
  medians **4.379 / 4.429 s** versus step 6 **4.450 / 4.460 s** (reduced/extended):
  **1.016 / 1.007x**. The large slowdown already reproduces on the prerequisite;
  this does not establish a causal breakdown or performance guarantee.
  `python /tmp/step06-comparison.py` creates the cell comparison; exact analysis
  scripts are archived in the companion evidence.
- `python baseline/native_limits.py` reproduces all four recorded native limits
  unchanged. A direct native planning SDD check records manager dimensions and
  counts: partial projection retains 135 native dimensions versus 44 active
  atoms, so native overflow occurs before dimension removal. No Python repair
  or backend substitution was added. Extended large counts also remain unreliable.
- Independent read-only review of commits `612b8ef` / `1d3a756` independently
  passed **763 library checks** and **4 recorder/reporting checks**, finding only
  a missing replay-environment export and an unused helper. Both were fixed in
  `ddf8e54` / `4f9ac8f`; affected session checks pass (**86 tests**).
- Ruff: `ruff check tddnnf tests examples` and companion `ruff check scripts tests
  baseline/run.py baseline/summarize.py baseline/test_recorder.py baseline/test_summary.py`.
  `git diff <base> --name-only --diff-filter=ACM` selects changed Python files
  for `ruff format --check` (16 library, 6 companion). Both `git diff <base>
  --check` checks pass. Relative Markdown links resolve; external HTTP links were
  not probed. Original baseline's 47 files outside the four updated recorder/
  reporting Python sources remain byte-identical, including its checksum manifest.
- Limits: matrix tasks are sequential, but short verification processes overlapped
  warm-up and early repeat 1. CPU affinity/frequency and unrelated host load are
  uncontrolled. Peak RSS is GNU Time child accounting, not a simultaneous sum;
  8 GiB is per-process address space, not a shared RSS cgroup limit. Skipped
  deferred features, dependency changes, historical regeneration, malformed-native
  probes and unrelated formatting. Removing old contexts/builders intentionally
  breaks their callers; native precision, overflow, buffering and zero-feature
  restrictions remain. Final evidence review and open companion PR links follow.
