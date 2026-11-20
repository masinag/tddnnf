from collections.abc import Mapping

import z3
from pysmt.environment import Environment
from pysmt.fnode import FNode
from pysmt.logics import QF_BOOL
from pysmt.solvers.z3 import Z3Solver

from tddnnf.core.pysmt_utils import is_atom


class CNFConverter:
    """Convert a Boolean abstraction to integer CNF without extending its vocabulary."""

    def convert(self, phi: FNode, atom_ids: Mapping[FNode, int]) -> tuple[list[list[int]], int]:
        """Convert phi into a list of clauses representing its Tseiting CNF encoding.

        `phi`'s atoms are mapped to integers according to the `atom_ids` mapping.
        Note that the method accepts the explicit mapping of an `Abstractor` instance, so Tseitin variables do not
        "pollute" the `Abstractor` known atoms.

        Args:
            phi: The formula to convert.
            atom_ids: Mapping from PySMT atoms to integer ids, used in the CNF representation

        Returns:
            tuple[list[list[int]], int]: A tuple containing:

            - a list of clauses where a clause is a list of the signed integers representing its literals.
            - the number of variables.
        """
        if any(not is_atom(atom) or atom.is_bool_constant() for atom in atom_ids):
            raise ValueError("Expected Boolean symbols or theory atoms")
        if any(idx <= 0 for idx in atom_ids.values()) or len(set(atom_ids.values())) != len(atom_ids):
            raise ValueError("Atom IDs must be unique positive integers")
        with Environment() as fresh:
            mgr = fresh.formula_manager
            phi = mgr.normalize(phi)
            atom_ids = {mgr.normalize(atom): idx for atom, idx in atom_ids.items()}
            occurring = fresh.ao.get_atoms(phi)
            if not occurring <= atom_ids.keys():
                raise ValueError("Formula atoms must have declared IDs")

            proxies = {atom: mgr.FreshSymbol() for atom in atom_ids}
            skeleton = fresh.substituter.substitute(phi, {atom: proxies[atom] for atom in occurring})
            solver = Z3Solver(environment=fresh, logic=QF_BOOL)
            with solver:
                converter = solver.converter
                ids = {converter.convert(proxy): atom_ids[atom] for atom, proxy in proxies.items()}
                variable_count = max(atom_ids.values(), default=0)
                ctx = solver.z3.ctx
                goal = z3.Goal(ctx=ctx)
                goal.add(converter.convert(skeleton))
                result = z3.Then(z3.Tactic("simplify", ctx=ctx), z3.Tactic("tseitin-cnf", ctx=ctx))(goal)
                clauses = []
                for clause in result[0]:
                    if z3.is_true(clause):
                        continue
                    if z3.is_false(clause):
                        return [[]], variable_count
                    literals = clause.children() if z3.is_or(clause) else [clause]
                    encoded = []
                    for literal in literals:
                        negative = z3.is_not(literal)
                        variable = literal.arg(0) if negative else literal
                        assert z3.is_const(variable) and z3.is_bool(variable), "Expected a Boolean CNF literal"
                        if variable not in ids:
                            variable_count += 1
                            ids[variable] = variable_count
                        encoded.append(-ids[variable] if negative else ids[variable])
                    clauses.append(encoded)
                return clauses, variable_count
