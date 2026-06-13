from tddnnf.compilers.cudd import BddCompiler
from tddnnf.queries.bdd_engine import BddEngine
from tests._base_engine_test import BaseTestEngine


class TestBddEngine(BaseTestEngine):
    compiler_cls = BddCompiler
    engine_cls = BddEngine
