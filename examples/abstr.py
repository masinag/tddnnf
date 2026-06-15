# ---- IMPORTS ----

from pysmt.shortcuts import GT, Not, Or, Plus, Real, Symbol
from pysmt.typing import REAL

from tddnnf.builders.reduced import TReducedBuilder
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.queries.bdd_engine import BddEngine
from tddnnf.queries.d4_engine import D4Engine
from tddnnf.queries.sdd_engine import SddEngine

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

# ---- BACKEND LOOP ----

print(f"phi: {phi}")

for name, compiler, qengine in [
    ("BDD", BddCompiler, BddEngine),
    ("SDD", SddCompiler, SddEngine),
    ("dDNNF", D4Compiler, D4Engine),
]:
    print(f"=== T-Reduced ({name}) ===")
    abstr = Abstractor()
    target = TReducedBuilder(compiler(abstr)).build(phi, [], abstr, project_on=atoms)
    engine = qengine(target)
    print(f"Is sat under assumpions {assumptions}? (unsound) {engine.is_satisfiable([assumptions])}")
