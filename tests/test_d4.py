import os
import tempfile

import pytest
from ddnnife import Ddnnf

from tddnnf.compilers.d4 import D4_BIN, D4CompiledTarget, D4Compiler
from tests._base_compiler_test import BaseTestCompiler

pytestmark = pytest.mark.skipif(
    not D4_BIN.is_file(),
    reason="d4 binary not installed (run: python -m tddnnf.install_bin --d4)",
)


def _has_root_nnf(nnf_text: str, node_type: str, node_id: int = 1) -> bool:
    return any(ln.startswith(f"{node_type} {node_id}") for ln in nnf_text.splitlines())


def _rc(target: D4CompiledTarget) -> int:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nnf", delete=False) as f:
        f.write(target.nnf_text)
        tmppath = f.name
    try:
        ddnnf = Ddnnf.from_file(tmppath, target.var_count)
        return int(str(ddnnf.rc()))
    finally:
        os.unlink(tmppath)


class TestD4Compiler(BaseTestCompiler):
    compiler_cls = D4Compiler
    target_cls = D4CompiledTarget

    def _count(self, target: D4CompiledTarget) -> int:
        if target.var_count == 0:
            return 0 if _has_root_nnf(target.nnf_text, "f") else 1
        if _has_root_nnf(target.nnf_text, "f"):
            return 0
        return _rc(target)

    def _is_true(self, target: D4CompiledTarget) -> bool:
        if target.var_count == 0:
            return _has_root_nnf(target.nnf_text, "t")
        return _rc(target) == (1 << target.var_count)

    def _is_false(self, target: D4CompiledTarget) -> bool:
        if target.var_count == 0:
            return _has_root_nnf(target.nnf_text, "f")
        if _has_root_nnf(target.nnf_text, "f"):
            return True
        return _rc(target) == 0
