from pysmt.environment import Environment
from pysmt.fnode import FNode


def owns_dag(formula: FNode, environment: Environment) -> bool:
    pending = [formula]
    seen = set()
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        if node not in environment.formula_manager:
            return False
        seen.add(node)
        pending.extend(node.args())
    return True


def equivalent(env: Environment, given: FNode, expected: FNode) -> bool:
    mgr = env.formula_manager
    with env.factory.Solver(name="z3") as solver:
        return solver.is_valid(mgr.Iff(given, expected))


def satisfiable(env: Environment, formula: FNode) -> bool:
    with env.factory.Solver(name="z3") as solver:
        solver.add_assertion(formula)
        return solver.solve()


def theory_models(env: Environment, formula: FNode, atoms: tuple[FNode, ...]) -> set[tuple[bool, ...]]:
    mgr = env.formula_manager
    models = set()
    with env.factory.Solver(name="z3") as solver:
        solver.add_assertion(formula)
        while solver.solve():
            values = tuple(solver.get_value(atom).is_true() for atom in atoms)
            models.add(values)
            solver.add_assertion(mgr.Or([mgr.Not(atom) if value else atom for atom, value in zip(atoms, values)]))
    return models
