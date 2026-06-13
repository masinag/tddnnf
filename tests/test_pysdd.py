from tddnnf.compilers.pysdd import SddCompiledTarget, SddCompiler
from tests._base_compiler_test import BaseTestCompiler


class TestSddCompiler(BaseTestCompiler):
    compiler_cls = SddCompiler
    target_cls = SddCompiledTarget

    def _count(self, target) -> int:
        return target.root.model_count()

    def _is_true(self, target) -> bool:
        return target.root.is_true()

    def _is_false(self, target) -> bool:
        return target.root.is_false()
