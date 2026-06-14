from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Self

import pysmt.operators as op
from pysmt.fnode import FNode
from pysmt.walkers import DagWalker, handles

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import PropCompiledTarget, PropCompiler

D4_BIN = Path(__file__).resolve().parent.parent / "bin" / "d4.bin"


class D4CompiledTarget(PropCompiledTarget):
    """A compiled d-DNNF target backed by a d4 NNF file."""

    def __init__(self, nnf_text: str, var_count: int, remapping: dict[int, int] | None = None) -> None:
        self._nnf_text = nnf_text
        self._var_count = var_count
        self._remapping = remapping if remapping is not None else {}

    @property
    def nnf_text(self) -> str:
        return self._nnf_text

    @property
    def var_count(self) -> int:
        return self._var_count

    @property
    def remapping(self) -> dict[int, int]:
        return self._remapping

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "circuit.nnf").write_text(self._nnf_text)
        (directory / "metadata.json").write_text(
            json.dumps(
                {
                    "var_count": self._var_count,
                    "remapping": {str(k): v for k, v in self._remapping.items()},
                }
            )
        )

    @classmethod
    def load(cls, directory: Path) -> Self:
        nnf_text = (directory / "circuit.nnf").read_text()
        metadata = json.loads((directory / "metadata.json").read_text())
        remapping = {int(k): v for k, v in metadata.get("remapping", {}).items()}
        return cls(nnf_text, metadata["var_count"], remapping=remapping)


class BCS12Walker(DagWalker):
    """Walks a pysmt formula, generating BC-S1.2 circuit gate definitions."""

    def __init__(self, abstractor: Abstractor) -> None:
        DagWalker.__init__(self, invalidate_memoization=True)
        self._abs = abstractor
        self._gate_counter = 0
        self._gate_lines: list[str] = []

    @property
    def gate_lines(self) -> list[str]:
        return self._gate_lines

    def _map(self, formula: FNode) -> str:
        return f"v{self._abs.get_id(formula)}"

    @staticmethod
    def _remove_double_neg(s: str) -> str:
        return s.replace("--", "")

    def walk_symbol(self, formula: FNode, args: tuple, **kwargs: object) -> str | None:
        if not formula.is_symbol():
            return None
        if formula not in self._abs:
            return None
        return self._map(formula)

    @handles(*op.CONSTANTS)
    def walk_constant(self, formula: FNode, args: tuple, **kwargs: object) -> str | None:
        if not formula.is_bool_constant():
            return None
        self._gate_counter += 1
        gate = f"g{self._gate_counter}"
        if formula.is_true():
            self._gate_lines.append(f"G {gate} := O v1 -v1")
        else:
            self._gate_lines.append(f"G {gate} := A v1 -v1")
        return gate

    @handles(*op.THEORY_OPERATORS)
    def walk_theory_op(self, formula: FNode, args: tuple, **kwargs: object) -> None:
        return None

    @handles(*op.RELATIONS)
    def walk_theory_atom(self, formula: FNode, args: tuple, **kwargs: object) -> str | None:
        if formula not in self._abs:
            return None
        return self._map(formula)

    def walk_and(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        if None in args:
            raise ValueError("AND node with invalid children")
        self._gate_counter += 1
        gate = f"g{self._gate_counter}"
        self._gate_lines.append(f"G {gate} := A " + " ".join(set(args)))
        return gate

    def walk_or(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        if None in args:
            raise ValueError("OR node with invalid children")
        self._gate_counter += 1
        gate = f"g{self._gate_counter}"
        self._gate_lines.append(f"G {gate} := O " + " ".join(set(args)))
        return gate

    def walk_not(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        if args[0] is None:
            raise ValueError("NOT node with invalid child")
        return self._remove_double_neg(f"-{args[0]}")

    def walk_implies(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        if args[0] is None or args[1] is None:
            raise ValueError("IMPLIES node with invalid children")
        self._gate_counter += 1
        gate = f"g{self._gate_counter}"
        line = f"G {gate} := O -{args[0]} {args[1]}"
        self._gate_lines.append(self._remove_double_neg(line))
        return gate

    def walk_iff(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        if args[0] is None or args[1] is None:
            raise ValueError("IFF node with invalid children")
        g1 = f"g{self._gate_counter + 1}"
        g2 = f"g{self._gate_counter + 2}"
        g3 = f"g{self._gate_counter + 3}"
        self._gate_counter += 3
        self._gate_lines.append(f"G {g1} := A {args[0]} {args[1]}")
        line = f"G {g2} := A -{args[0]} -{args[1]}"
        self._gate_lines.append(self._remove_double_neg(line))
        self._gate_lines.append(f"G {g3} := O {g1} {g2}")
        return g3

    def walk_ite(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        if args[0] is None or args[1] is None or args[2] is None:
            raise ValueError("ITE node with invalid children")
        g1 = f"g{self._gate_counter + 1}"
        g2 = f"g{self._gate_counter + 2}"
        g3 = f"g{self._gate_counter + 3}"
        self._gate_counter += 3
        self._gate_lines.append(f"G {g1} := O -{args[0]} {args[1]}")
        self._gate_lines.append(f"G {g2} := O {args[0]} {args[2]}")
        self._gate_lines.append(f"G {g3} := A {g1} {g2}")
        return g3

    def translate(self, formula: FNode) -> str:
        self._gate_counter = 0
        self._gate_lines.clear()
        result = self.walk(formula)
        assert result is not None, f"walk returned None for {formula}"
        return result


class D4Compiler(PropCompiler[D4CompiledTarget]):
    """PropCompiler that compiles an SMT formula into a d-DNNF via d4v2.

    The formula is first translated to BC-S1.2 circuit format, then compiled
    by the d4 binary. The resulting NNF is packaged into a D4CompiledTarget.
    """

    def __init__(self, abstractor: Abstractor) -> None:
        self._abstractor: Abstractor = abstractor

    def _register_atoms(self, atoms: list[FNode], project_on: list[FNode] | None) -> set[FNode]:
        proj_set: set[FNode]
        if project_on is not None:
            proj_set = set(project_on)
        else:
            proj_set = set(atoms)
        all_atoms = list(atoms)
        if project_on is not None:
            all_atoms.extend(a for a in project_on if a not in atoms)
        for atom in all_atoms:
            self._abstractor.get_id(atom)
        return proj_set

    def _write_circuit(
        self,
        formula: FNode,
        all_atom_ids: list[int],
        projected_ids: set[int],
        path: Path,
    ) -> None:
        walker = BCS12Walker(self._abstractor)
        root_gate = walker.translate(formula)

        with open(path, "w") as f:
            f.write("c BC-S1.2\n")
            for aid in all_atom_ids:
                f.write(f"I v{aid}\n")
            ids = sorted(projected_ids)
            if ids:
                f.write("P " + " ".join(f"v{i}" for i in ids) + "\n")
            else:
                f.write("P\n")
            for line in walker.gate_lines:
                f.write(line + "\n")
            f.write(f"T {root_gate}\n")

    @staticmethod
    def _run_d4(circuit_path: Path, out_path: Path) -> None:
        cmd = [
            str(D4_BIN),
            "-i",
            str(circuit_path),
            "--input-type",
            "circuit",
            "--remove-gates",
            "1",
            "--dump-file",
            str(out_path),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"d4 compilation failed (exit {result.returncode}):\n{result.stderr.decode()}")

    def compile(self, formula: FNode, project_on: list[FNode] | None = None) -> D4CompiledTarget:
        atoms = list(formula.get_atoms())
        if not atoms and (project_on is None or len(project_on) == 0):
            if formula.is_true():
                return D4CompiledTarget("t 1\n", 0)
            if formula.is_false():
                return D4CompiledTarget("f 1\n", 0)

        proj_set = self._register_atoms(atoms, project_on)

        all_atoms = set(atoms)
        if project_on is not None:
            all_atoms.update(project_on)
        all_atom_ids = sorted({self._abstractor.get_id(a) for a in all_atoms})

        projected_ids = {self._abstractor.get_id(a) for a in proj_set}

        with tempfile.TemporaryDirectory(prefix="d4_compile_") as tmpdir:
            tmp = Path(tmpdir)
            circuit_path = tmp / "circuit.bc"
            out_path = tmp / "output.nnf"

            self._write_circuit(formula, all_atom_ids, projected_ids, circuit_path)
            self._run_d4(circuit_path, out_path)

            if len(projected_ids) == 0:
                nnf_raw = out_path.read_text()
                if nnf_raw.startswith("f"):
                    return D4CompiledTarget("f 1\n", 0, remapping={})
                return D4CompiledTarget("t 1\n", 0, remapping={})

            nnf_text = out_path.read_text()
            if nnf_text.startswith("f"):
                return D4CompiledTarget("f 1\n", 0, remapping={})

        var_count = len(projected_ids)
        remapping = {aid: i + 1 for i, aid in enumerate(sorted(projected_ids))}
        return D4CompiledTarget(nnf_text, var_count, remapping=remapping)
