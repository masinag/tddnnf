# ---- IMPORTS ----

from enumerators.solvers.mathsat_total import MathSATTotalEnumerator
from pysmt.shortcuts import GT, And, Not, Or, Plus, Real, Symbol
from pysmt.typing import REAL

from tddnnf.builders.reduced import TReducedBuilder
from tddnnf.compilers.cudd import BddCompiler
from tddnnf.compilers.d4 import D4Compiler
from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.core.abstraction import Abstractor
from tddnnf.normalization import normalizer
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
phi = Or(And(xgt0, ygt5), And(xgt5, xpygt5))
clause = Or(xgt5, xpygt5)
assumptions = [Not(ygt5), Not(xgt0)]
atoms = [xgt5, xgt0, ygt5, xpygt5]

# ---- NORMALIZATION ----

normalizer = normalizer.NormalizerWalker()
# Normalization is needed!
phi = normalizer.normalize(phi)
atoms = [natom.arg(0) if (natom := normalizer.normalize(atom)).is_not() else natom for atom in atoms]
clause = normalizer.normalize(clause)
assumptions = [normalizer.normalize(assumption) for assumption in assumptions]

# ---- LEMMA ENUMERATION ----

enumerator = MathSATTotalEnumerator()
enumerator.check_all_sat(phi, atoms=atoms)
lemmas = enumerator.get_theory_lemmas()
lemmas = [normalizer.normalize(lemma) for lemma in lemmas]

# ---- OUTPUT ----

print(f"phi: {phi}")
print(f"Lemmas from phi ({len(lemmas)}):")
for lem in lemmas:
    print(f"  {lem}")

# ---- BACKEND LOOP ----

for name, compiler, qengine in [
    ("BDD", BddCompiler, BddEngine),
    ("SDD", SddCompiler, SddEngine),
    ("dDNNF", D4Compiler, D4Engine),
]:
    print(f"=== T-Reduced ({name}) ===")
    abstr = Abstractor()
    target = TReducedBuilder(compiler(abstr)).build(phi, lemmas, abstr, project_on=atoms)
    engine = qengine(target)

    print(f"Is sat under assumpions {assumptions}? {engine.is_satisfiable(assumptions)}")
    print(f"Entails {clause}? {engine.entails_clause(clause)}")
    print(f"Model count: {engine.count_truth_assignments()}")
    print("Models:")
    for m in engine.enumerate_truth_assignments():
        print(f"  {m}")
