from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tddnnf.queries.sdd_engine import SddEngine
from tests._base_engine_test import BaseTestEngine


class TestSddEngine(BaseTestEngine[SddCompiledTarget]):
    compiler_cls = SddCompiler
    engine_cls = SddEngine
