from tddnnf.compilers.d4 import D4Compiler
from tddnnf.queries.d4_engine import D4Engine
from tests._base_engine_test import BaseTestEngine


class TestD4Engine(BaseTestEngine):
    compiler_cls = D4Compiler
    engine_cls = D4Engine
