from __future__ import annotations

from io import StringIO

import pysmt.operators as op
from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode
from pysmt.smtlib.parser import SmtLibParser
from pysmt.smtlib.script import smtlibscript_from_formula
from pysmt.typing import BOOL
from pysmt.walkers import DagWalker, handles

from tddnnf.core.pysmt_utils import SuspendTypeChecking, is_atom


class _AbstractionWalker(DagWalker):
    """Walks an SMT DAG, replacing theory atoms with fresh Boolean variables."""

    def __init__(self, ctx: AbstractionContext, env: Environment | None = None) -> None:
        DagWalker.__init__(self, env)
        self._ctx = ctx

    @handles(*op.RELATIONS, op.FUNCTION)
    def walk_theory(self, formula: FNode, args: tuple[FNode, ...], **kwargs: object) -> FNode:
        bool_var = self._ctx.get_bool(formula)
        return self.env.formula_manager.Symbol(str(bool_var), BOOL)

    @handles(op.SYMBOL, *op.CONSTANTS, *op.THEORY_OPERATORS)
    def walk_noop(self, formula: FNode, args: tuple[FNode, ...], **kwargs: object) -> FNode:
        return formula

    @handles(*op.BOOL_CONNECTIVES, op.ITE)
    def walk_bool_op(self, formula: FNode, args: tuple[FNode, ...], **kwargs: object) -> FNode:
        if formula.is_not():
            return self.env.formula_manager.Not(args[0])
        return self.env.formula_manager.create_node(formula.node_type(), tuple(args))

    def walk(self, formula: FNode, **kwargs: object) -> FNode:
        with SuspendTypeChecking(self.env):
            return super().walk(formula, **kwargs)


class AbstractionContext:
    """Bidirectional map between SMT theory atoms and propositional Boolean variables."""

    def __init__(self, abstraction: dict[int, FNode] | None, env: Environment | None) -> None:
        self._env = env or get_env()
        self._bool_to_smt: dict[int, FNode] = abstraction if abstraction is not None else {}
        self._smt_to_bool: dict[FNode, int] = {atom: idx for idx, atom in self._bool_to_smt.items()}
        self._walker = _AbstractionWalker(self, self._env)

    def get_bool(self, smt_atom: FNode) -> int:
        assert is_atom(smt_atom)
        idx = self._smt_to_bool.get(smt_atom)
        if idx is None:
            idx = len(self._smt_to_bool) + 1
            self._smt_to_bool[smt_atom] = idx
            self._bool_to_smt[idx] = smt_atom
        return idx

    def get_smt(self, bool_var: int) -> FNode:
        if bool_var <= 0:
            raise ValueError(f"expected positive bool_var, got {bool_var}")
        return self._bool_to_smt[bool_var]

    def abstract(self, smt_formula: FNode) -> FNode:
        return self._walker.walk(smt_formula)

    def to_dict(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for atom, idx in self._smt_to_bool.items():
            script = smtlibscript_from_formula(atom)
            buf = StringIO()
            script.serialize(buf, daggify=False)
            result[buf.getvalue()] = idx
        return result

    @classmethod
    def from_dict(cls, data: dict[str, int], env: Environment | None = None) -> AbstractionContext:
        env = env or get_env()
        mgr = env.formula_manager
        bool_to_smt = {}
        parser = SmtLibParser(env)
        for smtlib_str, idx in data.items():
            script = parser.get_script(StringIO(smtlib_str))
            atom = script.get_last_formula(mgr)
            assert atom is not None
            bool_to_smt[idx] = atom
        return cls(bool_to_smt, env)
