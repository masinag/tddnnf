import json
from pathlib import Path

import pytest
from pysmt.environment import Environment, get_env
from pysmt.formula import FormulaManager

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize
from tddnnf.core.persistence import write_metadata
from tddnnf.core.theory_compiled_target import TheoryCompiledTarget


class ConjunctionTarget:
    def __init__(self, *atom_ids: int):
        self.atom_ids = atom_ids

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager):
        return mgr.And([abstr.get_atom(idx) for idx in self.atom_ids])

    def dag_size(self):
        return DagSize(3, 2)

    def save(self, directory: Path):
        directory.mkdir()
        (directory / "atoms.json").write_text(json.dumps(self.atom_ids))
        write_metadata(directory, "test-conjunction", codec="json", files=["atoms.json"])

    @classmethod
    def load(cls, directory: Path):
        return cls(*json.loads((directory / "atoms.json").read_text()))


def test_bindings_and_atoms_copy(env: Environment) -> None:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p"), mgr.Symbol("q")
    backend = ConjunctionTarget(7, 2)
    abstr = Abstractor({7: p, 2: q})
    atoms = [q, p]
    target = TheoryCompiledTarget(backend, abstr, atoms=atoms)

    atoms.clear()
    abstr.get_id(mgr.Symbol("later"))

    assert target.target is backend
    assert target.abstr is abstr
    assert target.env is env
    assert target.atoms == (q, p)
    assert target.abstr.get_atom(8) is mgr.Symbol("later")
    for name, replacement in (("target", backend), ("abstr", abstr), ("env", env), ("atoms", ())):
        with pytest.raises(AttributeError):
            setattr(target, name, replacement)


@pytest.mark.parametrize("explicit", [False, True])
def test_reconstruction_and_size_use_bound_target_and_environment(env: Environment, assert_owned_dag, explicit) -> None:
    destination = Environment() if explicit else env
    mgr = destination.formula_manager
    p, q = mgr.Symbol("p"), mgr.Symbol("q")
    backend = ConjunctionTarget(7, 2)
    target = TheoryCompiledTarget(
        backend, Abstractor({7: p, 2: q}), atoms=[q, p], env=destination if explicit else None
    )

    assert get_env() is env
    assert target.env is destination
    reconstructed = target.to_pysmt()
    assert reconstructed is mgr.And(p, q)
    assert_owned_dag(reconstructed, destination)
    assert target.dag_size() == DagSize(3, 2)
    assert get_env() is env


@pytest.mark.parametrize("explicit", [False, True])
def test_round_trip_preserves_abstraction_and_atoms(
    tmp_path: Path, env: Environment, explicit: bool, assert_owned_dag
) -> None:
    mgr = env.formula_manager
    p, q = mgr.Symbol("p"), mgr.Symbol("q")
    abstr = Abstractor({7: p, 2: q})
    target = TheoryCompiledTarget(ConjunctionTarget(7, 2), abstr, atoms=[q, p])
    abstr.get_id(mgr.Symbol("later"))
    directory = tmp_path / "target"
    target.save(directory)
    payload = json.loads((directory / "abstraction.json").read_text())
    assert payload == {"abstraction": abstr.to_dict(), "atom_ids": [2, 7]}

    with Environment() as current:
        destination = Environment() if explicit else current
        if explicit:
            loaded = TheoryCompiledTarget.load(directory, ConjunctionTarget, env=destination)
        else:
            loaded = TheoryCompiledTarget.load(directory, ConjunctionTarget)
        dest_mgr = destination.formula_manager
        dest_p, dest_q = dest_mgr.Symbol("p"), dest_mgr.Symbol("q")
        assert type(loaded.target) is ConjunctionTarget
        assert loaded.target.atom_ids == (7, 2)
        assert loaded.env is destination
        assert loaded.abstr.id_to_atom == {7: dest_p, 2: dest_q, 8: dest_mgr.Symbol("later")}
        assert loaded.atoms == (dest_q, dest_p)
        reconstructed = loaded.to_pysmt()
        assert reconstructed is dest_mgr.And(dest_p, dest_q)
        assert_owned_dag(reconstructed, destination)
        assert get_env() is current
    assert get_env() is env


def test_constant_round_trip_has_empty_vocabulary(tmp_path: Path, env: Environment, assert_owned_dag) -> None:
    target = TheoryCompiledTarget(ConjunctionTarget(), Abstractor(), atoms=[])
    directory = tmp_path / "target"
    target.save(directory)
    loaded = TheoryCompiledTarget.load(directory, ConjunctionTarget)

    assert loaded.env is env
    assert loaded.atoms == ()
    assert loaded.abstr.id_to_atom == {}
    reconstructed = loaded.to_pysmt()
    assert reconstructed is env.formula_manager.TRUE()
    assert_owned_dag(reconstructed, env)

    metadata = json.loads((directory / "metadata.json").read_text())
    assert metadata == {
        "schema_version": 1,
        "representation": "test-conjunction",
        "codec": "json",
        "files": ["atoms.json", "abstraction.json"],
    }
    assert json.loads((directory / "atoms.json").read_text()) == []
    assert json.loads((directory / "abstraction.json").read_text()) == {"abstraction": {}, "atom_ids": []}


@pytest.mark.parametrize("binding", ["abstraction", "atoms"])
def test_constructor_rejects_foreign_inputs(env: Environment, binding) -> None:
    mgr = env.formula_manager
    local = mgr.Symbol("p")
    foreign = Environment().formula_manager.Symbol("p")
    assert foreign is not local
    abstr = Abstractor({1: foreign if binding == "abstraction" else local})
    atoms = [foreign] if binding == "atoms" else [local]
    with pytest.raises(AssertionError, match="selected environment"):
        TheoryCompiledTarget(ConjunctionTarget(1), abstr, atoms=atoms, env=env)
