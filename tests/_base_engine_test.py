import itertools

import pytest
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.containers import TheoryCompiledTarget
from tddnnf.core.interfaces import PropCompiler, QueryEngine
from tests.conftest import SolverGroundTruth


class BaseTestEngine:
    compiler_cls: type[PropCompiler]
    engine_cls: type[QueryEngine]
    _skip_queries: frozenset[str] = frozenset()

    @pytest.fixture
    def compiler(self, abstr: Abstractor) -> PropCompiler:
        return self.compiler_cls(abstr)

    @pytest.fixture
    def engine(self, compiler: PropCompiler, abstr: Abstractor, mgr: FormulaManager, a: FNode, b: FNode) -> QueryEngine:
        target = compiler.compile(mgr.And(a, b))
        return self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))

    def test_exhaustive_engine_and_solver_space(
        self, mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth
    ) -> None:
        target = compiler.compile(bank_case.original_formula, project_on=bank_case.project_on)
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=bank_case.project_on))

        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(bank_case.expected_formula)
            solver_has_models = solver.solve()
        assert engine.is_satisfiable() == solver_has_models

        engine_pos_list = list(engine.enumerate_truth_assignments())
        assert len(engine_pos_list) == engine.count_truth_assignments()

        engine_pos_set = {frozenset(asg.items()) for asg in engine_pos_list}

        projected_vars = bank_case.project_on
        all_combinations = itertools.product([True, False], repeat=len(projected_vars))

        all_pos_conjunctions = []
        all_neg_conjunctions = []

        for combo in all_combinations:
            asg = dict(zip(projected_vars, combo))
            asg_frozen = frozenset(asg.items())

            conj = mgr.And([v if val else mgr.Not(v) for v, val in asg.items()])

            if asg_frozen in engine_pos_set:
                all_pos_conjunctions.append(conj)

                assert engine.is_implicant(conj)

                with mgr.env.factory.Solver() as solver:
                    solver.add_assertion(mgr.And(conj, mgr.Not(bank_case.expected_formula)))
                    assert not solver.solve(), f"Engine model {asg} is logically rejected by the SMT solver!"
            else:
                all_neg_conjunctions.append(conj)

                assert not engine.is_implicant(conj)

                with mgr.env.factory.Solver() as solver:
                    solver.add_assertion(mgr.And(conj, bank_case.expected_formula))
                    assert not solver.solve(), f"Engine missed a valid solver assignment: {asg}"

                entailed_clause = mgr.Or(*[mgr.Not(v) if val else v for v, val in asg.items()])
                assert engine.entails_clause(entailed_clause)

                with mgr.env.factory.Solver() as solver:
                    solver.add_assertion(mgr.And(bank_case.expected_formula, mgr.Not(entailed_clause)))
                    assert not solver.solve()

        pos_disjunction = mgr.Or(*all_pos_conjunctions) if all_pos_conjunctions else mgr.FALSE()
        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(mgr.And(bank_case.expected_formula, mgr.Not(pos_disjunction)))
            assert not solver.solve(), "Engine positive model enumeration failed completeness proof!"

        neg_disjunction = mgr.Or(*all_neg_conjunctions) if all_neg_conjunctions else mgr.FALSE()
        with mgr.env.factory.Solver() as solver:
            solver.add_assertion(mgr.And(mgr.Not(bank_case.expected_formula), mgr.Not(neg_disjunction)))
            assert not solver.solve(), "Engine counter-model state coverage is incomplete!"

    def test_queries_with_assumptions(
        self, mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, bank_case: SolverGroundTruth
    ) -> None:
        target = compiler.compile(bank_case.original_formula, project_on=bank_case.project_on)
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=bank_case.project_on))

        projected_vars = bank_case.project_on
        if not projected_vars:
            return

        valid_models = []
        all_combinations = itertools.product([True, False], repeat=len(projected_vars))
        for combo in all_combinations:
            asg = dict(zip(projected_vars, combo))
            conj = mgr.And([v if val else mgr.Not(v) for v, val in asg.items()])

            with mgr.env.factory.Solver() as solver:
                solver.add_assertion(mgr.And(conj, bank_case.expected_formula))
                if solver.solve():
                    valid_models.append(asg)

        #  Pick a small subset of the projected variables to act as our assumptions
        indices = {0, len(projected_vars) // 2, len(projected_vars) - 1}
        assume_vars = [projected_vars[i] for i in sorted(indices)][:3]
        assume_combinations = itertools.product([True, False], repeat=len(assume_vars))

        for assume_combo in assume_combinations:
            assume_dict = dict(zip(assume_vars, assume_combo))
            assumptions = [v if val else mgr.Not(v) for v, val in assume_dict.items()]

            expected_count = 0
            for model in valid_models:
                if all(model[v] == assume_dict[v] for v in assume_vars):
                    expected_count += 1

            expected_sat = expected_count > 0

            assert engine.is_satisfiable(assumptions=assumptions) == expected_sat, (
                f"Engine sat under assumptions {assume_dict} failed."
            )

            assert engine.count_truth_assignments(assumptions=assumptions) == expected_count, (
                f"Engine model count under assumptions {assume_dict} failed."
            )

    # --- Error / Validation Tests ---

    def test_is_satisfiable_unknown_assumption(self, engine: QueryEngine, c: FNode) -> None:
        with pytest.raises(ValueError, match="not a care variable"):
            engine.is_satisfiable(assumptions=[c])

    def test_count_truth_assignments_unknown_assumption(self, engine: QueryEngine, c: FNode) -> None:
        with pytest.raises(ValueError, match="not a care variable"):
            engine.count_truth_assignments(assumptions=[c])

    def test_entails_clause_unknown_atom(self, engine: QueryEngine, c: FNode) -> None:
        with pytest.raises(ValueError, match="not a care variable"):
            engine.entails_clause(c)

    def test_is_implicant_unknown_atom(self, engine: QueryEngine, c: FNode) -> None:
        with pytest.raises(ValueError, match="not a care variable"):
            engine.is_implicant(c)

    def test_is_implicant_invalid_input(self, engine: QueryEngine, mgr: FormulaManager, a: FNode, b: FNode) -> None:
        with pytest.raises(ValueError):
            engine.is_implicant(mgr.Or(a, b))

    def test_projected_assumption_on_forgotten_var_raises(
        self, mgr: FormulaManager, compiler: PropCompiler, abstr: Abstractor, a: FNode, b: FNode, c: FNode
    ) -> None:
        target = compiler.compile(mgr.And(a, mgr.Or(b, c)), project_on=[a, b])
        engine = self.engine_cls(TheoryCompiledTarget(target, abstr, care_vars=[a, b]))
        with pytest.raises(ValueError, match="not a care variable"):
            engine.is_satisfiable(assumptions=[c])
        with pytest.raises(ValueError, match="not a care variable"):
            engine.count_truth_assignments(assumptions=[c])
