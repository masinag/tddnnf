from tddnnf.compilers.d4 import D4CompiledTarget, D4Compiler
from tddnnf.queries.ddnnife_engine import DdnnifeEngine
from tests._base_engine_test import BaseTestEngine


class TestDdnnifeEngine(BaseTestEngine[D4CompiledTarget]):
    compiler_cls = D4Compiler
    engine_cls = DdnnifeEngine
