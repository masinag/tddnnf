from tddnnf.compilers.pysdd import SddCompiler
from tddnnf.queries.sdd_engine import SddEngine
from tests._base_engine_test import BaseTestEngine


class TestSddEngine(BaseTestEngine):
    compiler_cls = SddCompiler
    engine_cls = SddEngine
