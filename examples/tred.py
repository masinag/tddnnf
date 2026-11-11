# ---- IMPORTS ----

from pysmt.shortcuts import GT, And, Not, Or, Plus, Real, Symbol
from pysmt.typing import REAL
from tlemma_enum.solvers.mathsat_total import MathSATTotalEnumerator

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.queries import BddEngine, DdnnifeEngine, SddEngine

# ---- SMT ATOMS ----

x = Symbol("x", REAL)
y = Symbol("y", REAL)

# ---- FORMULAS ----

xgt5 = GT(x, Real(5))
xgt0 = GT(x, Real(0))
ygt5 = GT(y, Real(5))
xpygt5 = GT(Plus(x, y), Real(5))
phi = Or(And(xgt0, ygt5), And(xgt5, xpygt5))
clause = Or(xgt5, xpygt5)
assumptions = [Not(ygt5), Not(xgt0)]
atoms = [xgt5, xgt0, ygt5, xpygt5]

# ---- COMPILATION SESSION ----

with TheoryCompilation(phi, project_on=atoms) as compilation:
    # ---- LEMMA ENUMERATION ----

    enumerator = MathSATTotalEnumerator()
    enumerator.check_all_sat(compilation.phi, atoms=compilation.project_on)
    lemmas = enumerator.get_theory_lemmas()

    # ---- OUTPUT ----

    print(f"phi: {compilation.phi}")
    print(f"Lemmas from phi ({len(lemmas)}):")
    for lem in lemmas:
        print(f"  {lem}")

    # ---- BACKEND LOOP ----

    for name, compiler, engine_type in [
        ("BDD", BddCompiler, BddEngine),
        ("SDD", SddCompiler, SddEngine),
        ("dDNNF", D4Compiler, DdnnifeEngine),
    ]:
        print(f"=== T-Reduced ({name}) ===")
        target = compilation.compile_treduced(compiler(), lemmas)
        with target.queries(engine_type) as engine:
            print(f"Is sat under assumpions {assumptions}? {engine.is_satisfiable(assumptions)}")
            print(f"Entails {clause}? {engine.entails_clause(clause)}")
            print(f"Model count: {engine.count_truth_assignments()}")
            print("Models:")
            for m in engine.enumerate_truth_assignments():
                print(f"  {m}")
