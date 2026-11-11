# d-DNNF Modulo Theories

`tddnnf` is a Python library for compiling and querying d-DNNF Modulo Theories.
It compiles SMT formulas into d-DNNF, SDD, or OBDD representations and supports polytime
queries over the compiled result.

The framework’s compilation and query interfaces operate on SMT formulas represented
using [PySMT](https://github.com/pysmt/pysmt).

The framework implements the following paper:

[1] [G. Masina, E. Civini, M. Michelutti, G. Spallitta, and R. Sebastiani,
"d-DNNF Modulo Theories: A General Framework for Polytime SMT Queries," in SAT 2026](doi.org/10.4230/LIPIcs.SAT.2026.25).

Theory-lemma enumeration is done using the [tlemma_enum package](https://github.com/ecivini/tlemmas-enumeration/tree/develop) implementing the paper:

[2] [E. Civini, G. Masina, G. Spallitta, and R. Sebastiani,
"Beyond Eager Encodings: A Theory-Agnostic Approach to Theory-Lemma Enumeration in SMT,"
in IJCAR 2026](https://doi.org/10.1007/978-3-032-32589-1_18).

## Installation

The project requires Python 3.12 or newer and Git.

```bash
git clone https://github.com/masinag/tddnnf.git
cd tddnnf
python -m pip install .
pysmt-install --msat
```

Install the d4 compiler to use the d-DNNF backend:

```bash
python -m tddnnf.install_bin --d4
```

## Example

The following example compiles an SMT formula with the T-reduced strategy, then
runs satisfiability, entailment, and model-counting queries on the resulting
d-DNNF.

First, import the SMT, lemma-enumeration, compilation, and query dependencies.

```python
from pysmt.shortcuts import Symbol
from pysmt.typing import REAL
from tlemma_enum.solvers import (
    DivideByProjectedEnumerationStrategy,
    MathSATDivideAndConquerEnumerator,
)

from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.queries import DdnnifeEngine
```

Define the SMT atoms and formula.

```python
x = Symbol("x", REAL)
y = Symbol("y", REAL)

x_gt_5 = x > 5
x_gt_0 = x > 0
y_gt_5 = y > 5
x_plus_y_gt_5 = x + y > 5
phi = (x_gt_0 & y_gt_5) | (x_gt_5 & x_plus_y_gt_5)
```

Alternatively, load `phi` from an SMT-LIB file through PySMT.

```python
from pysmt.shortcuts import read_smtlib

phi = read_smtlib("formula.smt2")
```

Create the compilation context. Its `project_on` vocabulary determines which
atoms remain in the compiled target and may appear in queries. When omitted, as
here, it defaults to the atoms in `phi`. A custom `project_on` may select atoms
from `phi` as well as atoms that occur only in theory lemmas supplied at
compilation. Any atom in `phi` or those lemmas that is omitted from `project_on`
is existentially quantified away.

```python
compilation = TheoryCompilation(phi)
```

Enumerate theory lemmas for the normalized formula, passing the complete
projection vocabulary through `atoms=compilation.project_on`. This allows the
enumerator to generate lemmas involving query-only theory atoms that do not
occur in `phi`.

```python
enumerator = MathSATDivideAndConquerEnumerator(
    parallel_procs=4,
    divide_strategy=DivideByProjectedEnumerationStrategy(),
)
enumerator.check_all_sat(compilation.phi, atoms=compilation.project_on)
lemmas = enumerator.get_theory_lemmas()
```

See the [`tlemma_enum` repository](https://github.com/ecivini/tlemmas-enumeration/tree/develop)
for all available enumerators, enumeration strategies, configuration options,
and alternatives.

Compile the formula and its lemmas with the T-reduced strategy and d4 backend.

```python
target = compilation.compile_treduced(D4Compiler(), lemmas)
```

The target retains read-only bindings to its environment, abstraction, and tuple
vocabulary after compilation closes. Reconstruct with `target.to_pysmt()` and
inspect DAG metrics with `target.dag_size()`. `Abstractor.get_id()` registers new
atoms above the current maximum ID and preserves existing IDs. Constructor
mappings are copied and public mapping views are read-only. Builders reuse a
supplied abstractor; later registrations preserve earlier targets’ query
dimensions. Concurrent mutation is unsupported; saved mappings may include atoms
registered by later compilations.

Open a query session with the matching engine. Each session normalizes queries
in the target’s environment and aligns them with its stored vocabulary.

```python
engine = target.queries(DdnnifeEngine)
```

Run queries over that vocabulary.

```python
assumptions = [~y_gt_5, ~x_gt_0]
clause = x_gt_5 | x_plus_y_gt_5

print(engine.is_satisfiable(assumptions))
print(engine.entails_clause(clause))
print(engine.count_truth_assignments())
print(engine.count_truth_assignments(assumptions))
engine.close()
```

The expected output is:

```text
False
True
3
0
```

## Available components

### Compilation backends

Each compiler produces a different representation and must be paired with its
matching engine.

| Compiler | Representation | Engine | Requirement |
| --- | --- | --- | --- |
| `D4Compiler` | d-DNNF | `DdnnifeEngine` | Installed d4 binary |
| `SddCompiler` | SDD through PySDD | `SddEngine` | PySDD dependency |
| `BddCompiler` | OBDD through CUDD | `BddEngine` | `dd` with CUDD support |

To swap backends, change the compiler and engine together. For example, the
earlier workflow can use SDD as follows:

```python
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.queries import SddEngine

target = compilation.compile_treduced(SddCompiler(), lemmas)
with target.queries(SddEngine) as queries:
    print(queries.count_truth_assignments())
```

Compiler arguments must be instances, for example `D4Compiler()`, rather than
classes or strings. Instances can be reused: abstractions and computation logs
belong to each call. `SddCompiler(vtree_type="balanced", auto_gc_and_minimize=True)`
accepts vtree types `right`, `left`, `vertical`, `balanced`, and `random`, rejecting
invalid names before entering native code. Its Boolean option jointly controls
native automatic garbage collection and minimization. Pass `False` to disable both;
callers must respect the annotated argument types.

`TheoryCompilation` supports `with` and idempotent `close()`; normalization and
compilation fail after closure. `CompilationContext` remains an alias during
migration. Inputs must be Boolean nodes from the selected PySMT environment,
including every descendant; type hints and environment membership are caller
preconditions, without repeated runtime validation. Projection entries normalize
to positive Boolean symbols or theory atoms. Atoms that normalize to constants,
including negated atoms, are discarded; explicitly supplied constants and
compound Boolean entries are rejected.
Omitted projection uses normalized formula atoms in SMT-LIB serialization order;
explicit projection preserves first occurrence, including an empty list or atoms
absent from the formula and lemmas. Each compile call registers new projection
atoms first, then the remaining new combined-formula atoms in serialization order,
preserving any IDs in a supplied abstraction.
Non-projection atoms and encoding auxiliaries are existentially eliminated.

### Compilation strategies

Use the high-level `TheoryCompilation` methods for compilation.

| Method                | Lemmas enumerated for | Compiled formula                                         |
| --------------------- | --------------------- | -------------------------------------------------------- |
| `compile_treduced()`  | `phi`                 | `phi` conjoined with its theory lemmas                   |
| `compile_textended()` | `Not(phi)`            | `phi` disjoined with the negation of those theory lemmas |

### Query operations

All query sessions expose the same operations.

| Operation                                   | Result                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------- |
| `is_satisfiable(assumptions=None)`          | Whether the target has a satisfying truth assignment, optionally under literals |
| `count_truth_assignments(assumptions=None)` | Number of satisfying total truth assignments, optionally under literals         |
| `is_valid()`                                | Whether every truth assignment satisfies the target                             |
| `entails_clause(query_clause)`              | Whether the target entails a clause                                             |
| `is_implicant(query_cube)`                  | Whether a cube implies the target                                               |
| `enumerate_truth_assignments()`             | Iterator over satisfying total truth assignments                                |

Sessions accept engine classes; strings, engine instances, and incompatible
backend pairings raise `TypeError`. Use `with target.queries(BddEngine)` or call
idempotent `close()`. Each enumeration call creates an independent generator.
The session owns active enumerations and stops them before releasing native query
resources and the normalizer, even if cleanup raises. An enumeration can also be
closed explicitly with its own `close()` method. Query methods then raise `RuntimeError`; closed generators
raise `StopIteration`. The target and other sessions remain usable. Direct engines
and builders remain available. The former `QueryContext.wrap_queries()` API is
replaced by `target.queries(Engine)`.


Session clause/cube methods accept a single `FNode`; clauses and cubes may nest
their respective Boolean connective. Sessions flatten and align every literal,
then delegate the list to the matching engine method. Direct engines instead
require `entails_clause(query_clause: list[FNode])` and
`is_implicant(query_cube: list[FNode])`, with flat literals using exact stored
projection atoms. An empty clause is false and an empty cube is true. This breaks
compatibility for direct engine callers and custom engines using the former
formula signatures; migrate both methods to lists. Assumption signatures remain
unchanged, accepting literal lists.

Every input is validated before a semantic shortcut. Unknown and
inactive atoms, malformed formulas, and ambiguous canonical vocabularies raise
`ValueError`. Equivalent theory syntax and reversed polarity are aligned to the
exact stored atoms. Contradictory assumptions yield `False`/`0`; tautological
clauses and contradictory cubes yield `True`. Constants and empty inputs follow
Boolean semantics. Enumerated dictionaries contain every active atom in projection
order, including unconstrained atoms absent from the DAG.

Reasoning remains native: CUDD counting uses floating point, PySDD global counts
can overflow, and ddnnife enumeration buffers results and has a u64 size limit.
Derived validity and implicant answers for d-DNNF inherit native count limits.
See [REFACTOR.md](REFACTOR.md) for installed versions and baseline reproductions.

## Saving lemmas and compiled targets

Since compilation can be expensive, intermediate results can be stored on disk and
loaded later.

Prepare an artifact directory and persistence imports. This example continues
from the d4 walkthrough above.

```python
from pathlib import Path

from pysmt.shortcuts import And, read_smtlib, write_smtlib

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget

artifact_dir = Path("artifacts")
artifact_dir.mkdir(exist_ok=True)
```

Save the enumerated lemmas as an SMT-LIB formula.

```python
lemmas_file = artifact_dir / "lemmas.smt2"
write_smtlib(And(lemmas), lemmas_file)
```

Load the SMT-LIB formula and recover the original lemma list.

```python
lemmas_formula = read_smtlib(str(lemmas_file))
if lemmas_formula.is_true():
    loaded_lemmas = []
elif lemmas_formula.is_and():
    loaded_lemmas = list(lemmas_formula.args())
else:
    loaded_lemmas = [lemmas_formula]
```

Compile from the loaded lemmas and save the target.

```python
target = compilation.compile_treduced(D4Compiler(), loaded_lemmas)
target_dir = artifact_dir / "ddnnf"
target.save(target_dir)
```

Reload the target without compiling again; versioned metadata selects its backend.
The destination passed to `save()` must not already exist. Standalone backend
save/load methods use the same versioned metadata and their backend libraries.
Unversioned artifacts require the companion testbench's `scripts/migrate_compiled_targets.py`; they are never guessed
by the library loader. Saved artifacts are package-owned state: loading checks
only the schema version,
then reconstructs directly from metadata, abstraction, and native payloads. Codec
and file declarations describe the artifact by convention; they are not a
validation contract. Malformed or manually edited artifacts may load incorrectly,
raise ordinary exceptions, or crash CUDD/PySDD readers. d4 loading preserves NNF
text without certifying graph correctness. Migration contains native-reader failures in a
subprocess.

```python
loaded_target = TheoryCompiledTarget.load(target_dir, D4CompiledTarget)
```

Open a session and query the loaded target.

```python
with loaded_target.queries(DdnnifeEngine) as queries:
    print(queries.count_truth_assignments())
```

See the [`examples/`](examples/) directory for more examples.

External backends can implement `PropCompiledTarget` structurally, without
inheritance or registration. For example, this target stores one abstraction ID:

```python
from pathlib import Path

from pysmt.environment import Environment

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import DagSize
from tddnnf.core.persistence import metadata, saving_to, write_metadata


class LiteralTarget:
    def __init__(self, atom_id: int):
        self.atom_id = atom_id

    def dag_size(self):
        return DagSize(1, 0)

    def to_pysmt(self, abstr, mgr):
        return abstr.get_atom(self.atom_id)

    def save(self, directory):
        with saving_to(directory) as temporary:
            temporary.mkdir()
            (temporary / "literal.txt").write_text(str(self.atom_id))
            write_metadata(temporary, "literal", codec="integer-text", files=["literal.txt"])

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        metadata(directory)
        return cls(int((directory / "literal.txt").read_text()))


env = Environment()
atom = env.formula_manager.Symbol("a")
target = TheoryCompiledTarget(LiteralTarget(7), Abstractor({7: atom}), [atom], env)
target.save(Path("literal-target"))
loaded = TheoryCompiledTarget.load(Path("literal-target"), LiteralTarget, env=env)
assert loaded.to_pysmt() is atom
```

The container writes `abstraction.json` and adds it to the backend's declared
payload files. `load` requires a target class and preserves its concrete type;
representation and codec metadata are descriptive and do not select a backend.
Applications should check representation metadata before calling native loaders
when they need to reject a mismatch with their selected backend.
