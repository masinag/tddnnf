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

from tddnnf import CompilationContext, QueryContext
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.queries.d4_engine import D4Engine
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
here, it defaults to the normalized atoms in `phi`.

```python
compilation = CompilationContext(phi)
```

Enumerate theory lemmas for the normalized formula and its projection atoms.

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
target = compilation.compile_treduced(D4Compiler, lemmas)
```

Create the matching d4 query engine. `QueryContext.wrap_queries()` normalizes
query formulas and aligns their atoms with the target's projection vocabulary.

```python
engine = QueryContext(target).wrap_queries(D4Engine(target))
```

Run queries over that vocabulary.

```python
assumptions = [~y_gt_5, ~x_gt_0]
clause = x_gt_5 | x_plus_y_gt_5

print(engine.is_satisfiable(assumptions))
print(engine.entails_clause(clause))
print(engine.count_truth_assignments())
print(engine.count_truth_assignments(assumptions))
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
matching query engine.

| Compiler      | Representation    | Query engine | Requirement            |
| ------------- | ----------------- | ------------ | ---------------------- |
| `D4Compiler`  | d-DNNF            | `D4Engine`   | Installed d4 binary    |
| `SddCompiler` | SDD through PySDD | `SddEngine`  | PySDD dependency       |
| `BddCompiler` | OBDD through CUDD | `BddEngine`  | `dd` with CUDD support |

To swap backends, change the compiler and engine together. For example, the
earlier workflow can use SDD as follows:

```python
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.queries.sdd_engine import SddEngine

target = compilation.compile_treduced(SddCompiler, lemmas)
engine = QueryContext(target).wrap_queries(SddEngine(target))
```

### Compilation strategies

Use the high-level `CompilationContext` methods for compilation.

| Method                | Lemmas enumerated for | Compiled formula                                         |
| --------------------- | --------------------- | -------------------------------------------------------- |
| `compile_treduced()`  | `phi`                 | `phi` conjoined with its theory lemmas                   |
| `compile_textended()` | `Not(phi)`            | `phi` disjoined with the negation of those theory lemmas |

### Query operations

All matching query engines expose the same operations.

| Operation                                   | Result                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------- |
| `is_satisfiable(assumptions=None)`          | Whether the target has a satisfying truth assignment, optionally under literals |
| `count_truth_assignments(assumptions=None)` | Number of satisfying total truth assignments, optionally under literals         |
| `is_valid()`                                | Whether every truth assignment satisfies the target                             |
| `entails_clause(query_clause)`              | Whether the target entails a clause                                             |
| `is_implicant(query_cube)`                  | Whether a cube implies the target                                               |
| `enumerate_truth_assignments()`             | Iterator over satisfying total truth assignments                                |

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
target = compilation.compile_treduced(D4Compiler, loaded_lemmas)
target_dir = artifact_dir / "ddnnf"
target.save(target_dir)
```

Reload the d4 target without compiling again.

```python
loaded_target = TheoryCompiledTarget.load(target_dir, D4CompiledTarget)
```

Wrap the matching engine and query the loaded target.

```python
loaded_engine = QueryContext(loaded_target).wrap_queries(D4Engine(loaded_target))
print(loaded_engine.count_truth_assignments())
```

See the [`examples/`](examples/) directory for more examples.
