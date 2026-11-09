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
its companion PR then rather than postponing it to step 5 or 7.

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
| 3 | `refactor/03-target-ownership` | Private representations and bound immutable target state | 2 |
| 4 | `refactor/04-query-sessions` | Query composition, input handling, native delegation, cleanup | 3 |
| 5 | `refactor/05-persistence` | Versioned persistence and paired consumer migration | 4 |
| 6 | `refactor/06-ddnnf-conversion` | Explicit SDD/OBDD DAG conversion | 5 |
| 7 | `refactor/07-public-migration` | Public cleanup, examples, full validation | 6 |

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
non-projection variables, deterministic IDs across hash seeds, environment
validation, subprocess errors, and temporary cleanup. Run affected compiler,
abstraction, normalization, and compilation-context tests. Update broken
testbench callers in a companion PR if needed for these checks.

### Step 3 — target ownership

Introduce private representation objects and one public target bound to its
environment, abstraction, and immutable active vocabulary. Preserve native
manager/root lifetimes, reconstruction, and metrics.

Check targets after compilation-session closure, constants and shared DAGs,
mapping/vocabulary mutation attempts, reconstruction in the bound environment,
and native reordering/minimization without semantic change. Verify resource
cleanup on exceptions and retained root ownership. Run affected target,
compiler, reconstruction, and metrics tests. Public removal of transitional
entry points waits until step 7.

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
declared files. Distinguish an explicitly identified legacy SDD without a
vtree from a damaged modern artifact. Validate safe writes, refusal to
overwrite, and cleanup after failure.

Migration checks cover single, recursive, and dry-run modes; preserved IDs,
projection order, logs, and byte-identical native payloads; DDDMP order recovery;
existing and missing legacy SDD vtrees; and absence of recompilation. Run the
testbench serialization, compile-task, query-consumer, and migration tests
against the proposed library SHA. Record limitations where original structural
metadata cannot be recovered.

### Step 6 — d-DNNF conversion

Add `to_ddnnf()` using native DAG traversal and memoization. Existing d-DNNF
targets return themselves. Exercise constants, shared subgraphs, complemented
roots/edges, both literal polarities, and nontrivial native ID mappings. Verify
the conversion preserves abstraction, environment, ordered active vocabulary,
and source semantics without invoking a compiler or enumerating models.

Query converted SDD/OBDD targets through the d-DNNF reasoner using all six unary
operations on small fixtures. Round-trip converted NNF with its declared codec.
Check sharing structurally, not only by comparing truth tables. Separate
conversion errors from the reasoner's already documented native limitations.

### Step 7 — public migration

Migrate exports, examples, README, architecture documentation, and testbench
consumers to the final public interface. Remove obsolete public contexts,
builders, and backend target entry points after callers have moved. Simplify
affected tests into small functions and straightforward backend parameterization
while retaining useful helpers and coverage.

Run the complete library suite and affected testbench suite with the proposed
paired revisions. Execute the public examples and compare the fixed step-1
benchmarks, reporting timing, memory, size, and semantic differences. Stable ID
ordering may change native structure and performance; investigate regressions
instead of promising equal timings or byte-identical new compilations. Preserve
existing dependencies, logging, reconstruction, and metrics. Transformations,
relational queries, extra reasoners, and the Python d4 compiler stay deferred.

## Agent setup

Use one implementation agent with write access and reuse its session while the
context remains useful. Pause implementation during a fresh read-only review
of substantive committed changes, especially ownership, persistence, and DAG
conversion. Give the reviewer the step, relevant design sections, commit range,
connected callers, and test evidence; the entire planning conversation is
unnecessary. Routine documentation and mechanical changes need no extra agent.

| Role | Model | Effort |
| --- | --- | --- |
| Implementation | GPT-6.1 Sol | Medium |
| Difficult mapping/conversion | Same implementation agent | High |
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
merges. Steps 1 and 2 record their checks below; steps 3–7 have not started.

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
