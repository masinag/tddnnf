from tddnnf.compilers.cudd import BddCompiledTarget, BddCompiler
from tests._base_compiler_test import BaseTestCompiler


class TestBddCompiler(BaseTestCompiler):
    compiler_cls = BddCompiler
    target_cls = BddCompiledTarget
