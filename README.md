# d-DNNF Modulo Theories

`tddnnf` is a Python library for compiling and querying d-DNNF Modulo Theories (KCMT).
It compiles SMT formulas into d-DNNF, SDD, or OBDD representations and supports
queries over the compiled result.

The framework implements the following paper:
[1] [G. Masina, E. Civini, M. Michelutti, G. Spallitta, and R. Sebastiani,
"d-DNNF Modulo Theories: A General Framework for Polytime SMT Queries," in SAT 2026](doi.org/10.4230/LIPIcs.SAT.2026.25).

Theory-lemma enumeration is done using the [tlemma_enum package](https://github.com/ecivini/tlemmas-enumeration/tree/develop) implementing the paper:
[2] [E. Civini, G. Masina, G. Spallitta, and R. Sebastiani,
"Beyond Eager Encodings: A Theory-Agnostic Approach to Theory-Lemma Enumeration in SMT,"
in IJCAR 2026](https://doi.org/10.1007/978-3-032-32589-1_18)

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

x = Symbol("x", REAL)
y = Symbol("y", REAL)

# Formula definition
x_gt_5 = x > 5
x_gt_0 = x > 0
y_gt_5 = y > 5
x_plus_y_gt_5 = x + y > 5
phi = (x_gt_0 & y_gt_5) | (x_gt_5 & x_plus_y_gt_5)

compilation = CompilationContext(phi)

# Lemma enumeration
enumerator = MathSATDivideAndConquerEnumerator(
    parallel_procs=4,
    divide_strategy=DivideByProjectedEnumerationStrategy(),
)
enumerator.check_all_sat(compilation.phi, atoms=list(compilation.phi.get_atoms()))
lemmas = enumerator.get_theory_lemmas()

# Compilation
target = compilation.compile_treduced(D4Compiler, lemmas)
engine = QueryContext(target).wrap_queries(D4Engine(target))

# Querying
assumptions = [~y_gt_5, ~x_gt_0]
clause = x_gt_5 | x_plus_y_gt_5

print(engine.is_satisfiable(assumptions))
print(engine.entails_clause(clause))
print(engine.count_truth_assignments())
print(engine.count_truth_assignments(assumptions))
```

Expected output:

```text
False
True
3
0
```

## Saving lemmas and compiled targets

Compilation can be expensive. Intermediate results can be stored on disk and
loaded later.

```python
from pathlib import Path

from pysmt.shortcuts import And, read_smtlib, write_smtlib

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.containers import TheoryCompiledTarget

artifact_dir = Path("artifacts")
artifact_dir.mkdir(exist_ok=True)

# Save and load the theory lemmas.
lemmas_file = artifact_dir / "lemmas.smt2"
write_smtlib(And(lemmas), lemmas_file)

lemmas_formula = read_smtlib(str(lemmas_file))
if lemmas_formula.is_true():
    loaded_lemmas = []
elif lemmas_formula.is_and():
    loaded_lemmas = list(lemmas_formula.args())
else:
    loaded_lemmas = [lemmas_formula]

# Compile and save the d-DNNF target.
target = compilation.compile_treduced(D4Compiler, loaded_lemmas)
target_dir = artifact_dir / "ddnnf"
target.save(target_dir)

# Load without compiling again.
loaded_target = TheoryCompiledTarget.load(target_dir, D4CompiledTarget)

# Query
loaded_engine = QueryContext(loaded_target).wrap_queries(D4Engine(loaded_target))
print(loaded_engine.count_truth_assignments())
```

See the [`examples/`](examples/) directory for more examples.
