import pysmt.operators as op
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.shortcuts import get_env
from pysmt.walkers import DagWalker, handles

from tddnnf.core.pysmt_utils import SuspendTypeChecking


class NormalizerWalker(DagWalker):
    """Walks an SMT DAG, normalizing theory atoms through a Mathsat solver."""

    def __init__(self, env: Environment | None = None) -> None:
        self._env = env if env is not None else get_env()
        DagWalker.__init__(self, self._env)
        self._solver = self._env.factory.Solver("msat")
        self._converter = self._solver.converter

    def __del__(self) -> None:
        self._solver.exit()

    @property
    def mgr(self) -> FormulaManager:
        return self.env.formula_manager

    @handles(*op.RELATIONS, op.FUNCTION)
    def walk_theory(self, formula: FNode, args: tuple[FNode, ...], **kwargs: object) -> FNode:
        msat_term = self._converter.convert(formula)
        return self._converter.back(msat_term)

    @handles(op.SYMBOL, *op.CONSTANTS, *op.THEORY_OPERATORS)
    def walk_noop(self, formula: FNode, args: tuple[FNode, ...], **kwargs: object) -> FNode:
        return formula

    @handles(*op.BOOL_CONNECTIVES, op.ITE)
    def walk_bool_op(self, formula: FNode, args: tuple[FNode, ...], **kwargs: object) -> FNode:
        if formula.is_not():
            return self.mgr.Not(args[0])
        return self.mgr.create_node(formula.node_type(), tuple(args))

    def walk(self, formula: FNode, **kwargs: object) -> FNode:
        with SuspendTypeChecking(self.env):
            return super().walk(formula, **kwargs)

    def normalize(self, formula: FNode) -> FNode:
        return self.walk(formula)
