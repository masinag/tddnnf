"""Exact projected solver-model oracle shared by engine semantics and assumptions."""

from itertools import product


def solver_models(mgr, formula, atoms):
    """Return exact projected assignments accepted by the solver."""
    models = set()
    with mgr.env.factory.Solver() as solver:
        solver.add_assertion(formula)
        for values in product([True, False], repeat=len(atoms)):
            model = dict(zip(atoms, values))
            literals = [atom if value else mgr.Not(atom) for atom, value in model.items()]
            if solver.solve(assumptions=literals):
                models.add(frozenset(model.items()))
    return models
