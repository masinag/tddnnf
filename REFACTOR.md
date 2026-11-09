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
merges. Steps 1–7 have not started.

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
