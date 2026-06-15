from pysmt.fnode import FNode
from pysmt.formula import FormulaManager


def gen_true(mgr: FormulaManager, _: list[FNode]) -> FNode:
    return mgr.TRUE()


def gen_false(mgr: FormulaManager, _: list[FNode]) -> FNode:
    return mgr.FALSE()


def gen_simple_not(mgr: FormulaManager, v: list[FNode]) -> FNode:
    return mgr.Not(v[0])


def gen_simple_and(mgr: FormulaManager, v: list[FNode]) -> FNode:
    return mgr.And(v[0], v[1])


def gen_simple_or(mgr: FormulaManager, v: list[FNode]) -> FNode:
    return mgr.Or(v[0], v[1])


def gen_simple_nested(mgr: FormulaManager, v: list[FNode]) -> FNode:
    return mgr.And(mgr.Or(v[0], v[1]), v[2])


def gen_linear_chain(mgr: FormulaManager, v: list[FNode]) -> FNode:
    return mgr.And(*[mgr.Implies(v[i], v[i + 1]) for i in range(len(v) - 1)])


def gen_redundant_subtree(mgr: FormulaManager, v: list[FNode]) -> FNode:
    mid = len(v) // 2
    sub = mgr.Iff(v[0], v[1])
    left = mgr.And(*v[2:mid], sub)
    right = mgr.And(*v[mid:], sub)
    return mgr.Or(left, right)


def gen_deep_ite(mgr: FormulaManager, v: list[FNode]) -> FNode:
    if len(v) < 3:
        return mgr.And(*v)
    cur = v[-1]
    for i in range(len(v) - 3, -1, -1):
        cur = mgr.Or(mgr.And(v[i], v[i + 1]), mgr.And(mgr.Not(v[i]), cur))
    return cur


def gen_pigeonhole(mgr: FormulaManager, v: list[FNode]) -> FNode:
    clauses = [mgr.Not(mgr.And(v[i], v[j])) for i in range(len(v)) for j in range(i + 1, len(v))]
    return mgr.And(mgr.Or(*v), mgr.And(*clauses))


FORMULA_BANK: list[tuple] = [
    (gen_true, 1, "all"),
    (gen_false, 1, "all"),
    (gen_simple_not, 1, "all"),
    (gen_simple_and, 2, "all"),
    (gen_simple_or, 2, "all"),
    (gen_simple_nested, 3, "all"),
    (gen_simple_nested, 3, "first_k"),
    (gen_linear_chain, 4, "all"),
    (gen_linear_chain, 6, "first_k"),
    (gen_linear_chain, 8, "high_ids"),
    (gen_linear_chain, 10, "even"),
    (gen_linear_chain, 5, "odd"),
    (gen_redundant_subtree, 4, "first_k"),
    (gen_redundant_subtree, 6, "all"),
    (gen_redundant_subtree, 7, "odd"),
    (gen_redundant_subtree, 8, "high_ids"),
    (gen_redundant_subtree, 10, "even"),
    (gen_deep_ite, 4, "even"),
    (gen_deep_ite, 5, "all"),
    (gen_deep_ite, 7, "first_k"),
    (gen_deep_ite, 9, "high_ids"),
    (gen_deep_ite, 10, "odd"),
    (gen_pigeonhole, 4, "high_ids"),
    (gen_pigeonhole, 5, "first_k"),
    (gen_pigeonhole, 6, "even"),
    (gen_pigeonhole, 7, "all"),
    (gen_pigeonhole, 8, "odd"),
]
