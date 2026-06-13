from tddnnf.compilers.cudd import BddCompiledTarget, BddCompiler
from tests._base_compiler_test import BaseTestCompiler


class TestBddCompiler(BaseTestCompiler):
    compiler_cls = BddCompiler
    target_cls = BddCompiledTarget

    def _count(self, target) -> int:
        return int(target.root.count())

    def _is_true(self, target) -> bool:
        return target.root == target.manager.true

    def _is_false(self, target) -> bool:
        return target.root == target.manager.false
