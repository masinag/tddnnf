from typing import Self, cast

import pysmt.operators as op
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.shortcuts import get_env
from pysmt.solvers.msat import MathSAT5Solver, MSatConverter
from pysmt.walkers import DagWalker, handles

from tddnnf.core.pysmt_utils import SuspendTypeChecking


class NormalizerWalker(DagWalker):
    """Normalize theory atoms through MathSAT, using DagWalker's memoization.

    Callers must supply Boolean FNodes whose entire DAG belongs to the selected
    environment. Type hints and this environment precondition are trusted.
    """

    def __init__(self, env: Environment | None = None) -> None:
        self._closed = False
        self._solver = None
        self._env = env if env is not None else get_env()
        DagWalker.__init__(self, self._env)
        try:
            self._solver: MathSAT5Solver = self._env.factory.Solver("msat")
            self._converter = cast(MSatConverter, self._solver.converter)
        except BaseException:
            self.close()
            raise

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> Self:
        if self._closed:
            raise RuntimeError("Normalizer is closed")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Release the solver exactly once, including after partial initialization."""
        if not self._closed:
            self._closed = True
            if self._solver is not None:
                self._solver.exit()

    @property
    def mgr(self) -> FormulaManager:
        return self.env.formula_manager

    @handles(*op.RELATIONS)
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
        if self._closed:
            raise RuntimeError("Normalizer is closed")
        with SuspendTypeChecking(self.env):
            return super().walk(formula, **kwargs)

    def normalize(self, formula: FNode) -> FNode:
        return self.walk(formula)
