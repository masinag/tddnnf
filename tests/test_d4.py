import pytest

from tddnnf.compilers.d4 import D4_BIN, D4CompiledTarget, D4Compiler
from tests._base_compiler_test import BaseTestCompiler

pytestmark = pytest.mark.skipif(
    not D4_BIN.is_file(),
    reason="d4 binary not installed (run: python -m tddnnf.install_bin --d4)",
)


class TestD4Compiler(BaseTestCompiler):
    compiler_cls = D4Compiler
    target_cls = D4CompiledTarget
