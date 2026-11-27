# d-DNNF Modulo Theories

`tddnnf` is a Python library for compiling, transforming, and querying SMT
formulas in deterministic, decomposable negation normal form (d-DNNF) or some
stricter forms, like ordered binary decision diagrams (OBDDs) or sentential
decision diagrams (SDDs).

The framework implements the following papers:

[1]
[G. Masina, E. Civini, M. Michelutti, G. Spallitta, and R. Sebastiani, "d-DNNF Modulo Theories: A General Framework for Polytime SMT Queries", SAT 2026](https://doi.org/10.4230/LIPIcs.SAT.2026.25).

[2]
[M. Michelutti, G. Masina, G. Spallitta, and R. Sebastiani. "Canonical Decision Diagrams Modulo Theories", ECAI 2024](https://doi.org/10.3233/FAIA241007).

Theory-lemma enumeration is done using the
[tlemma_enum](https://github.com/ecivini/tlemmas-enumeration/tree/develop)
package.

## Overview

The key idea behind this framework is to combine an SMT formula with a suitable
set of theory lemmas so that SMT-level queries reduce to propositional-level
queries. The resulting formula can then be compiled ---by means of existing
propositional compilers--- into a target language that supports answering
propositional queries in polynomial time. By the property above, this also
allows SMT queries to be answered in polynomial time using existing
propositional reasoners.

We distinguish two classes of formulas, which can be obtained by combining the
original formula in different ways with different set of theory lemmas.

| Class           | Property                                                                             | How to obtain the property for a formula `phi`                                                                                                     |
| --------------- | ------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------- |
| Theory-reduced  | The formula is propositionally satisfied only by theory-consistent truth assignments | `phi ∧ ⋀ᵢ lᵢ`, where `{lᵢ}ᵢ` is a set of theory lemmas ruling out the theory-inconsistent truth assignments that propositionally satisfy `phi`     |
| Theory-extended | All the theory-inconsistent truth assignments propositionally satisfy the formula    | `phi ∨ ¬(⋀ᵢ kᵢ)`, where `{kᵢ}ᵢ` is a set of theory lemmas ruling out the theory-inconsistent truth assignments that propositionally satisfy `¬phi` |

Each class supports a different set of SMT queries that can be reduced to their
propositional counterparts.

| Class           |         CO         |         CE         |         IM         |         VA         |         EQ         |         SE         |         CT         |         ME         |
| --------------- | :----------------: | :----------------: | :----------------: | :----------------: | :----------------: | :----------------: | :----------------: | :----------------: |
| Theory-reduced  | :white_check_mark: | :white_check_mark: |                    |                    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Theory-extended |                    |                    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |                    |                    |

Where:

- **CO** (consistency): determine if the formula is theory-satisfiable.
- **CE** (clause entailment): determine if the formula theory-entails a clause.
- **IM** (implicant): determine if a cube theory-entails the formula.
- **VA** (validity): determine if the formula is theory-valid.
- **EQ** (equivalence): determine if two formulas are theory-equivalent.
- **SE** (sentence entailment): determine if a formulas theory-entails another
  formula.
- **CT** (counting): count the number of theory-satisfiable truth assignments.
- **ME** (model enumeration): enumerate all the theory-satisfiable truth
  assignments.

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
from tddnnf.compilation.d4 import D4Compiler
from tddnnf.queries import DdnnifeEngine, QuerySession

x = Symbol("x", REAL)
y = Symbol("y", REAL)

x_gt_5 = x > 5
x_gt_0 = x > 0
y_gt_5 = y > 5
x_plus_y_gt_5 = x + y > 5
phi = (x_gt_0 & y_gt_5) | (x_gt_5 & x_plus_y_gt_5)

# -------- compilation --------
with TheoryCompilation(phi) as compilation:
    # required theory lemmas can be enumerated via the tlemma_enum package
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
with QuerySession(tred_target, DdnnifeEngine) as engine:
    assumptions = [~y_gt_5, ~x_gt_0]
    clause = x_gt_5 | x_plus_y_gt_5
    print(f"Is T-SAT? {engine.is_satisfiable()}")
    print(f"Is T-SAT under assumptions {assumptions}? {engine.is_satisfiable(assumptions)}")
    print(f"T-entails {clause}? {engine.entails_clause(clause)}")
    print(f"# T-SAT truth assignments: {engine.count_truth_assignments()}")
    print(f"# T-SAT truth assignments under assumptions {assumptions}: {engine.count_truth_assignments(assumptions)}")

# -------- querying theory-extended --------
with QuerySession(text_target, DdnnifeEngine) as engine:
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

See the [`examples/`](examples/) directory for more examples.

## Available components

### Compilation backends

| Representation | Compiler                                                                                                                             |                        Requirements |
| :------------- | :----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------: |
| d-DNNF         | `D4Compiler` interface for [d4](https://github.com/crillab/d4v2)                                                                     | `python -m tddnnf.install_bin --d4` |
| OBDD           | `CuddCompiler` interface for [CUDD](https://web.archive.org/web/20180127051756/http://vlsi.colorado.edu/~fabio/CUDD/html/index.html) |                installed by default |
| SDD            | `PySddCompiler` interface for [PySDD](https://github.com/ML-KULeuven/PySDD)                                                          |                installed by default |

Each compiler produces a different representation and must be paired with its
matching engine(s).

### Query backends

| Representation | Compiler                                                                                                                           |                    Requirements |
| :------------- | :--------------------------------------------------------------------------------------------------------------------------------- | ------------------------------: |
| d-DNNF         | `DdnnifeEngine` interface for [ddnnife](https://github.com/practical-kc/ddnnife)                                                   |            installed by default |
| d-DNNF         | `DecDnnfRsEngine` interface for [decdnnf_rs_py](https://github.com/crillab/decdnnf_rs_py)                                          | `pip install 'tddnnf[decdnnf]'` |
| OBDD           | `CuddEngine` interface for [CUDD](https://web.archive.org/web/20180127051756/http://vlsi.colorado.edu/~fabio/CUDD/html/index.html) |            installed by default |
| SDD            | `PySddEngine` interface for [PySDD](https://github.com/ML-KULeuven/PySDD)                                                          |            installed by default |

For example, the above formula can be compiled into an SDD and queried via

```python
from tddnnf.compilation import PySddCompiler
from tddnnf.queries import QuerySession, PySddEngine

target = compilation.compile_treduced(PySddCompiler(), lemmas)
with QuerySession(target, PySddEngine) as queries:
    print(queries.count_truth_assignments())
```

### Compilation methods

The `TheoryCompilation` class is the entry point for compilation. It requires
specifying the formula `phi` to be compiled, and the set `atoms` of atoms that
used as the vocabulary for compilation and querying: `atoms` must be a superset
of the set of atoms occurring the in the formula `phi` and in the subsequent
queries.

`TheoryCompilation` provides two high-level methods for compiling theory-reduced
and theory-extended d-DNNF formulas:

- `compile_treduced(compiler, lemmas)`;
- `compile_textended(compiler, lemmas)`.

Each method requires a propositional compiler class, and a suitable set of
theory lemmas. For a correct result of the subsequent queries, the set of theory
lemmas must match the [above](#overview) requirements. **Importantly**, the set
of lemmas must rule out truth assignments over the whole `atoms` set, comprising
also those atoms that do not occur in `phi` but only in subsequent queries. A
convenient way to obtain such a set is by using the
[`tlemma_enum`](https://github.com/ecivini/tlemmas-enumeration/tree/develop)
package is by explicitly passing the atoms set as

```python
enumerator.check_all_sat(compilation.phi, atoms=list(compilation.atoms))
```

for theory-reduced compilation, or

```python
enumerator.check_all_sat(Not(compilation.phi), atoms=list(compilation.atoms))
```

for theory-extended compilation.

### Query operations

The `QuerySession` is the entry point for queries. It requires specifying a
compiled formula `theory_target` to be queries, and an propositional query
engine class `engine_type` be instantiated and used for answering queries.

Since all the queries are performed at the propositional level, the correctness
of the answers depends on the theory-reduction or theory-extension properties of
the supplied compiled formula, as from the [above table](#overview).

`QuerySession` exposes the following operations, corresponding to the
[above](#overview) queries:

- **CO**: `is_satisfiable(assumptions=None)`
- **CE**: `entails_clause(query_clause)`
- **IM**: `is_implicant(query_cube)`
- **VA**: `is_valid()`
- **CT**: `count_truth_assignments(assumptions=None)`
- **ME**: `enumerate_truth_assignments()`

## Saving lemmas and compiled targets

Since compilation can be expensive, intermediate results can be stored on disk
and loaded later.

Prepare an artifact directory and persistence imports. This example continues
from the walkthrough above.

```python
from pathlib import Path

from pysmt.shortcuts import And, read_smtlib, write_smtlib

artifact_dir = Path("artifacts")
artifact_dir.mkdir(exist_ok=True)

def save_lemmas(lemmas: list[FNode], lemmas_file: Path) -> None:
  """Save the enumerated lemmas as an SMT-LIB formula."""
  write_smtlib(And(lemmas), lemmas_file)

def load_lemmas(lemmas_file: Path) -> list[FNode]:
  """Load the SMT-LIB formula and recover the original lemma list."""
  lemmas_formula = read_smtlib(str(lemmas_file))
  if lemmas_formula.is_true():
      loaded_lemmas = []
  elif lemmas_formula.is_and():
      loaded_lemmas = list(lemmas_formula.args())
  else:
      loaded_lemmas = [lemmas_formula]

lemmas_file = artifact_dir / "lemmas.smt2"
save_lemmas(lemmas, lemmas_file)
loaded_lemmas = load_lemmas(lemmas_file)
```

Similarly, one can save and load the compiled target.

```python
from tddnnf.compilation.d4 import D4CompiledTarget

target_dir = artifact_dir / "ddnnf"

target.save(target_dir)
loaded_target = TheoryCompiledTarget.load(target_dir, D4CompiledTarget)
```

## Installation

The latest version of the package can be installed via

```bash
pip install git+https://github.com/masinag/tddnnf.git
```

The framework internally uses the SMT solver MathSAT, which must be installed
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
