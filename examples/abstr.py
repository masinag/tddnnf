# ---- IMPORTS ----

from pysmt.shortcuts import GT, Not, Or, Plus, Real, Symbol
from pysmt.typing import REAL

from tddnnf import TheoryCompilation
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.queries import BddEngine, D4Engine, SddEngine

# ---- SMT ATOMS ----

x = Symbol("x", REAL)
y = Symbol("y", REAL)

# ---- FORMULAS ----

xgt5 = GT(x, Real(5))
xgt0 = GT(x, Real(0))
ygt5 = GT(y, Real(5))
xpygt5 = GT(Plus(x, y), Real(5))
phi = Or(xgt0, xpygt5)
assumptions = [Not(ygt5), Not(xgt0)]
atoms = [xgt5, xgt0, ygt5, xpygt5]

# ---- COMPILATION CONTEXT ----

with TheoryCompilation(phi, project_on=atoms) as compilation:
    # ---- BACKEND LOOP ----

    print(f"phi: {phi}")

    for name, compiler, engine_type in [
        ("BDD", BddCompiler, BddEngine),
        ("SDD", SddCompiler, SddEngine),
        ("dDNNF", D4Compiler, D4Engine),
    ]:
        print(f"=== T-Reduced ({name}) ===")
        target = compilation.compile_treduced(compiler(), [])
        with target.queries(engine_type) as engine:
            print(f"Is sat under assumpions {assumptions}? (unsound) {engine.is_satisfiable(assumptions)}")
