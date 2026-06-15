from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tests._base_compiler_test import BaseTestCompiler


class TestSddCompiler(BaseTestCompiler):
    compiler_cls = SddCompiler
    target_cls = SddCompiledTarget
