# ---- IMPORTS ----

from pysmt.shortcuts import GT, And, Not, Or, Plus, Real, Symbol
from pysmt.typing import REAL
from tlemma_enum.solvers.mathsat_total import MathSATTotalEnumerator

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.queries import CuddReasoner, DdnnifeReasoner, SddReasoner

# ---- SMT ATOMS ----

x = Symbol("x", REAL)
y = Symbol("y", REAL)

# ---- FORMULAS ----

xgt5 = GT(x, Real(5))
xgt0 = GT(x, Real(0))
ygt5 = GT(y, Real(5))
xpygt5 = GT(Plus(x, y), Real(5))
phi = Or(xgt0, xpygt5)
cube = And(xgt5, ygt5)
atoms = list(phi.get_atoms() | cube.get_atoms())

# ---- COMPILATION CONTEXT ----

with TheoryCompilation(phi, project_on=atoms) as compilation:
    # ---- LEMMA ENUMERATION ----

    enumerator = MathSATTotalEnumerator()
    enumerator.check_all_sat(Not(compilation.phi), compilation.project_on)
    lemmas = enumerator.get_theory_lemmas()

    # ---- OUTPUT ----

    print(f"phi: {compilation.phi}")
    print(f"Lemmas from phi ({len(lemmas)}):")
    for lem in lemmas:
        print(f"  {lem}")

    # ---- BACKEND LOOP ----

    for name, compiler, reasoner in [
        ("BDD", BddCompiler, CuddReasoner),
        ("SDD", SddCompiler, SddReasoner),
        ("dDNNF", D4Compiler, DdnnifeReasoner),
    ]:
        print(f"=== T-Extended ({name}) ===")
        target = compilation.compile_textended(compiler(), lemmas)
        with target.queries(reasoner()) as engine:
            print(f"Valid? {engine.is_valid()}")
            print(f"{cube} is implicant? {engine.is_implicant(cube)}")
