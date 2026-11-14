import pytest
from pysmt.environment import Environment, get_env
from pysmt.fnode import FNode
from pysmt.typing import BOOL, INT, REAL

from tddnnf.core.abstraction import Abstractor


def make_atoms(env: Environment) -> tuple[FNode, ...]:
    mgr = env.formula_manager
    return (
        mgr.Symbol("p", BOOL),
        mgr.Symbol("q", BOOL),
        mgr.LE(mgr.Symbol("x", REAL), mgr.Real(0)),
        mgr.Equals(mgr.Symbol("n", INT), mgr.Int(1)),
    )


def test_registration_and_bidirectional_lookup(env: Environment) -> None:
    abstractor = Abstractor()
    assert abstractor.var_count == abstractor.max_var == 0
    assert abstractor.id_to_atom == abstractor.atom_to_id == {}
    for idx, atom in enumerate(make_atoms(env), start=1):
        assert atom not in abstractor
        assert abstractor.get_id(atom) == idx
        assert abstractor.get_id(atom) == idx
        assert atom in abstractor
        assert abstractor.get_atom(idx) == atom
    expected = dict(enumerate(make_atoms(env), start=1))
    assert abstractor.id_to_atom == expected
    assert abstractor.atom_to_id == {atom: idx for idx, atom in expected.items()}
    assert abstractor.var_count == abstractor.max_var == 4


def test_sparse_mapping(env: Environment) -> None:
    p, q, real_atom, _ = make_atoms(env)
    abstractor = Abstractor({2: p, 7: real_atom})
    assert abstractor.var_count == 2
    assert abstractor.max_var == 7
    assert abstractor.get_id(p) == 2
    assert abstractor.get_id(real_atom) == 7
    assert abstractor.get_id(q) == 8
    assert abstractor.var_count == 3
    assert abstractor.max_var == 8


def test_constructor_copies_input_and_mapping_views_are_live_and_read_only(env: Environment) -> None:
    p, q, real_atom, _ = make_atoms(env)
    supplied = {2: p}
    abstractor = Abstractor(supplied)
    supplied[2] = real_atom
    supplied[7] = q
    assert abstractor.id_to_atom == {2: p}
    assert abstractor.atom_to_id == {p: 2}

    id_to_atom = abstractor.id_to_atom
    atom_to_id = abstractor.atom_to_id
    with pytest.raises(TypeError):
        id_to_atom[3] = q  # pyright: ignore[reportIndexIssue]
    with pytest.raises(TypeError):
        atom_to_id[q] = 3  # pyright: ignore[reportIndexIssue]
    with pytest.raises(TypeError):
        del id_to_atom[2]  # pyright: ignore[reportIndexIssue]
    with pytest.raises(TypeError):
        del atom_to_id[p]
    assert abstractor.get_id(q) == 3
    assert id_to_atom == {2: p, 3: q}
    assert atom_to_id == {p: 2, q: 3}


@pytest.mark.parametrize("idx", [0, -1])
def test_get_atom_rejects_nonpositive_ids(env: Environment, idx: int) -> None:
    with pytest.raises(ValueError):
        Abstractor().get_atom(idx)


def test_get_atom_rejects_unknown_positive_id(env: Environment) -> None:
    abstractor = Abstractor({2: make_atoms(env)[0]})
    with pytest.raises(KeyError):
        abstractor.get_atom(3)


@pytest.mark.parametrize("ids", [(), (2, 5, 7, 11)], ids=["empty", "populated"])
def test_serialization_round_trip_in_default_environment(env: Environment, ids: tuple[int, ...]) -> None:
    original = Abstractor(dict(zip(ids, make_atoms(env))))
    serialized = original.to_dict()
    with Environment() as destination:
        restored = Abstractor.from_dict(serialized)
        expected = dict(zip(ids, make_atoms(destination)))
        assert get_env() is destination
        assert restored.id_to_atom == expected
        assert restored.atom_to_id == {atom: idx for idx, atom in expected.items()}


@pytest.mark.parametrize("ids", [(), (2, 5, 7, 11)], ids=["empty", "populated"])
def test_serialization_round_trip_in_explicit_environment(env: Environment, ids: tuple[int, ...]) -> None:
    original = Abstractor(dict(zip(ids, make_atoms(env))))
    destination = Environment()

    restored = Abstractor.from_dict(original.to_dict(), env=destination)

    expected = dict(zip(ids, make_atoms(destination)))
    assert get_env() is env
    assert destination is not env
    assert restored.id_to_atom == expected
    assert restored.atom_to_id == {atom: idx for idx, atom in expected.items()}


@pytest.mark.parametrize("value", [True, False])
def test_constructor_rejects_boolean_constants(env: Environment, value: bool) -> None:
    with pytest.raises(ValueError):
        Abstractor({2: make_atoms(env)[0], 7: env.formula_manager.Bool(value)})


@pytest.mark.parametrize("value", [True, False])
@pytest.mark.parametrize("populated", [False, True], ids=["empty", "populated"])
def test_failed_constant_registration_preserves_state(env: Environment, value: bool, populated: bool) -> None:
    p, q, real_atom, _ = make_atoms(env)
    expected = {2: p, 7: real_atom} if populated else {}
    abstractor = Abstractor(expected)
    id_to_atom = abstractor.id_to_atom
    atom_to_id = abstractor.atom_to_id
    constant = env.formula_manager.Bool(value)
    with pytest.raises(ValueError):
        abstractor.get_id(constant)
    assert constant not in abstractor
    assert id_to_atom == expected
    assert atom_to_id == {atom: idx for idx, atom in expected.items()}
    assert abstractor.var_count == len(expected)
    assert abstractor.max_var == (7 if populated else 0)
    assert abstractor.get_id(q) == (8 if populated else 1)


@pytest.mark.parametrize("value", [True, False])
def test_deserialization_rejects_standalone_boolean_constants(env: Environment, value: bool) -> None:
    script = f"(set-logic QF_BOOL)\n(assert {str(value).lower()})\n(check-sat)\n"
    with pytest.raises(ValueError):
        Abstractor.from_dict({script: 1})
