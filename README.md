# d-DNNF Modulo Theories

`tddnnf` is a Python library for compiling and querying SMT formulas in
deterministic, decomposable negation normal form (d-DNNF) or some stricter
forms, like ordered binary decision diagrams (OBDDs) or sentential decision
diagrams (SDDs).

## References

The framework implements the following papers:

[1]
[G. Masina, E. Civini, M. Michelutti, G. Spallitta, and R. Sebastiani, "d-DNNF Modulo Theories: A General Framework for Polytime SMT Queries", SAT 2026](https://doi.org/10.4230/LIPIcs.SAT.2026.25).

[2]
[M. Michelutti, G. Masina, G. Spallitta, and R. Sebastiani. "Canonical Decision Diagrams Modulo Theories", ECAI 2024](https://doi.org/10.3233/FAIA241007).

Theory-lemma enumeration is done using the
[tlemma_enum](https://github.com/ecivini/tlemmas-enumeration/tree/develop)
package, implementing the paper:

[3]
[E. Civini, G. Masina, G. Spallitta, and R. Sebastiani, "Beyond Eager Encodings: A Theory-Agnostic Approach to Theory-Lemma Enumeration in SMT," in IJCAR 2026](https://doi.org/10.1007/978-3-032-32589-1_18).

## Installation

The latest version of the package can be installed via

```bash
pip install git+https://github.com/masinag/tddnnf.git
```

The framework uses internally the SMT solver MathSAT, which must be installed
via:

```bash
pysmt-install --msat
```

For d-DNNF compilation with [d4](https://github.com/crillab/d4v2), install the
compiler with:

```bash
python -m tddnnf.install_bin --d4
```

Other compilers and queries are installed by default as python dependencies.

## Example

The framework’s compilation and query interfaces operate on SMT formulas
represented using [PySMT](https://github.com/pysmt/pysmt).

The following example compiles an SMT formula into a theory-reduced d-DNNF using
[d4](https://github.com/crillab/d4v2). Then, it runs satisfiability, clause
entailment, and model-counting queries on the resulting d-DNNF using
[ddnnife](https://github.com/practical-kc/ddnnife).

```python
from pysmt.shortcuts import Not, Symbol
from pysmt.typing import REAL
from tlemma_enum.solvers import MathSATTotalEnumerator

from tddnnf import TheoryCompilation
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.queries import DdnnifeEngine

x = Symbol("x", REAL)
y = Symbol("y", REAL)

x_gt_5 = x > 5
x_gt_0 = x > 0
y_gt_5 = y > 5
x_plus_y_gt_5 = x + y > 5
phi = (x_gt_0 & y_gt_5) | (x_gt_5 & x_plus_y_gt_5)

# -------- compilation --------
with TheoryCompilation(phi) as compilation:
    # Compilation into a theory-reduced or theory-extended representation requires
    # providing a set of theory lemmas for a specific formula and atom set. These
    # lemmas can be enumerated via the tlemma_enum package
    enumerator = MathSATTotalEnumerator()
    enumerator.check_all_sat(compilation.phi, atoms=list(compilation.atoms))
    phi_lemmas = enumerator.get_theory_lemmas()
    # compile theory-reduced formula
    tred_target = compilation.compile_treduced(D4Compiler(), phi_lemmas)

    enumerator.check_all_sat(Not(compilation.phi), atoms=list(compilation.atoms))
    not_phi_lemmas = enumerator.get_theory_lemmas()
    text_target = compilation.compile_textended(D4Compiler(), not_phi_lemmas)

print(f"Formula: {phi}")
print()
# -------- querying theory-reduced --------
with tred_target.queries(DdnnifeEngine) as engine:
    assumptions = [~y_gt_5, ~x_gt_0]
    clause = x_gt_5 | x_plus_y_gt_5
    print(f"Is T-SAT? {engine.is_satisfiable()}")
    print(f"Is T-SAT under assumptions {assumptions}? {engine.is_satisfiable(assumptions)}")
    print(f"T-entails {clause}? {engine.entails_clause(clause)}")
    print(f"# T-SAT truth assignments: {engine.count_truth_assignments()}")
    print(f"# T-SAT truth assignments under assumptions {assumptions}: {engine.count_truth_assignments(assumptions)}")

# -------- querying theory-extended --------
with text_target.queries(DdnnifeEngine) as engine:
    cube = x_gt_5 & x_plus_y_gt_5
    print(f"Is T-valid? {engine.is_valid()}")
    print(f"{cube} is T-implicant? {engine.is_implicant(cube)}")
```

The expected output is

```text
Formula: (((0.0 < x) & (5.0 < y)) | ((5.0 < x) & (5.0 < (x + y))))

Is T-SAT? True
Is T-SAT under assumptions [(! (5.0 < y)), (! (0.0 < x))]? False
T-entails ((5.0 < x) | (5.0 < (x + y)))? True
# T-SAT truth assignments: 3
# T-SAT truth assignments under assumptions [(! (5.0 < y)), (! (0.0 < x))]: 0
Is T-valid? False
((5.0 < x) & (5.0 < (x + y))) is T-implicant? True
```

See the
[`tlemma_enum`](https://github.com/ecivini/tlemmas-enumeration/tree/develop)
repository for all available enumerators, enumeration strategies, configuration
options, and alternatives.

## Available components

### Compilation backends

| Representation | Compiler                                                                                                                            |                        Requirements |
| :------------- | :---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------: |
| d-DNNF         | `D4Compiler` interface for [d4](https://github.com/crillab/d4v2)                                                                    | `python -m tddnnf.install_bin --d4` |
| OBDD           | `BddCompiler` interface for [CUDD](https://web.archive.org/web/20180127051756/http://vlsi.colorado.edu/~fabio/CUDD/html/index.html) |                installed by default |
| SDD            | `SddCompiler` interface for [PySDD](https://github.com/ML-KULeuven/PySDD)                                                           |                installed by default |

Each compiler produces a different representation and must be paired with its
matching engine(s).

### Query backends

| Representation | Compiler                                                                                                                          |          Requiremets |
| :------------- | :-------------------------------------------------------------------------------------------------------------------------------- | -------------------: |
| d-DNNF         | `DdnnifeEngine` interface for [ddnnife](https://github.com/practical-kc/ddnnife)                                                  | installed by default |
| OBDD           | `BddEngine` interface for [CUDD](https://web.archive.org/web/20180127051756/http://vlsi.colorado.edu/~fabio/CUDD/html/index.html) | installed by default |
| SDD            | `SddEngine` interface for [PySDD](https://github.com/ML-KULeuven/PySDD)                                                           | installed by default |

For example, the above formula can be compiled into an SDD and queried via

```python
from tddnnf.compilers import SddCompiler
from tddnnf.queries import SddEngine

target = compilation.compile_treduced(SddCompiler(), lemmas)
with target.queries(SddEngine) as queries:
    print(queries.count_truth_assignments())
```

### Compilation methods

Use the high-level `TheoryCompilation` methods for compilation.

| Method                | Requires lemmas enumerated for | Compiled formula                                         |
| --------------------- | ------------------------------ | -------------------------------------------------------- |
| `compile_treduced()`  | `phi`                          | `phi` conjoined with its theory lemmas                   |
| `compile_textended()` | `Not(phi)`                     | `phi` disjoined with the negation of those theory lemmas |

### Query operations

All query sessions expose the same operations. However, it must be noted that
the correctness of the result depends on the supplied target: some SMT queries
are correct only for theory-reduced formulas, some others only for
theory-extended formulas, some others for both. See [the paper](#references) for
details, and the table below for a summary.

| Operation                                   | Result                                                                          | Theory-Reduced     | Theory-Extended    |
| ------------------------------------------- | ------------------------------------------------------------------------------- | ------------------ | ------------------ |
| `is_satisfiable(assumptions=None)`          | Whether the target has a satisfying truth assignment, optionally under literals | :heavy_check_mark: |                    |
| `count_truth_assignments(assumptions=None)` | Number of satisfying total truth assignments, optionally under literals         | :heavy_check_mark: |                    |
| `is_valid()`                                | Whether every truth assignment satisfies the target                             |                    | :heavy_check_mark: |
| `entails_clause(query_clause)`              | Whether the target entails a clause                                             | :heavy_check_mark: |                    |
| `is_implicant(query_cube)`                  | Whether a cube implies the target                                               |                    | :heavy_check_mark: |
| `enumerate_truth_assignments()`             | Iterator over satisfying total truth assignments                                | :heavy_check_mark: |                    |

## Saving lemmas and compiled targets

Since compilation can be expensive, intermediate results can be stored on disk
and loaded later.

Prepare an artifact directory and persistence imports. This example continues
from the d4 walkthrough above.

```python
from pathlib import Path

from pysmt.shortcuts import And, read_smtlib, write_smtlib

from tddnnf.compilers.d4 import D4CompiledTarget
from tddnnf.core.theory_compiled_target import TheoryCompiledTarget

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

Load the target without compiling again by supplying its backend class.

```python
loaded_target = TheoryCompiledTarget.load(target_dir, D4CompiledTarget)
```

See the [`examples/`](examples/) directory for more examples.
