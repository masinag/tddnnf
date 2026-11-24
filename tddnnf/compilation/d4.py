from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Self

import pysmt.operators as op
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.walkers import DagWalker, handles

from tddnnf.compilation.cnf import CNFConverter
from tddnnf.compilation.compiler import PropCompiler
from tddnnf.compilation.targets import DagSize, PropCompiledTarget
from tddnnf.core.abstraction import Abstractor
from tddnnf.core.persistence import read_metadata, saving_to, write_metadata
from tddnnf.core.pysmt_utils import compilation_vocabulary
from tddnnf.core.stats_collector import StatsCollector

D4_BIN = Path(__file__).resolve().parent.parent / "bin" / "d4.bin"


def _clean_nnf(nnf_text: str, var_count: int) -> str:
    """Remove nonprojected edge literals that d4 can leave despite the declared projection.

    This ensures the compiled circuit only contains the projected variables. Projected variables occupy IDs
    1..var_count. No simplification is performed after removal.
    This operation should be safe, as leftover literals are just an artifact of compilation.
    """
    cleaned_lines = []
    for line in nnf_text.splitlines():
        parts = line.split()
        if parts and parts[0] not in ("t", "f", "o", "a"):
            literals = [lit for lit in parts[2:-1] if 1 <= abs(int(lit)) <= var_count]
            line = " ".join([*parts[:2], *literals, "0"])
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines) + "\n"


@dataclass
class _D4Node:
    node_type: str
    edges: list[tuple[int, list[int]]]

    def to_pysmt(
        self,
        formulas: Mapping[int, FNode],
        abstr: Abstractor,
        mgr: FormulaManager,
        inv_remap: Mapping[int, int],
    ) -> FNode:
        children = []
        for target, literals in self.edges:
            child = formulas[target]
            if literals:
                atoms = [abstr.get_atom(inv_remap[abs(lit)]) for lit in literals]
                child = mgr.And(child, *(atom if lit > 0 else mgr.Not(atom) for lit, atom in zip(literals, atoms)))
            children.append(child)
        if self.node_type in ("t", "f"):
            return mgr.Bool(self.node_type == "t")
        return mgr.Or(children) if self.node_type == "o" else mgr.And(children)


class D4CompiledTarget(PropCompiledTarget):
    """A compiled d-DNNF target backed by a d4 NNF file."""

    def __init__(self, nnf_text: str, var_count: int, remapping: Mapping[int, int] | None = None) -> None:
        self._nnf_text = nnf_text
        self._var_count = var_count
        self._remapping = MappingProxyType(dict(remapping) if remapping else {i: i for i in range(1, var_count + 1)})

    @property
    def nnf_text(self) -> str:
        return self._nnf_text

    @property
    def var_count(self) -> int:
        return self._var_count

    @property
    def remapping(self) -> Mapping[int, int]:
        return self._remapping

    def dag_size(self) -> DagSize:
        vertices = edges = 0
        for _, node in self._walk_nodes():
            vertices += 1
            edges += len(node.edges)
        return DagSize(vertices, edges)

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        inv_remap = {v: k for k, v in self._remapping.items()}
        formulas: dict[int, FNode] = {}
        for node_id, node in self._walk_nodes():
            formulas[node_id] = node.to_pysmt(formulas, abstr, mgr, inv_remap)
        return formulas[1]

    def _walk_nodes(self) -> Iterator[tuple[int, _D4Node]]:
        graph: dict[int, _D4Node] = {}
        edges: dict[int, list[tuple[int, list[int]]]] = {}
        for line_number, line in enumerate(self._nnf_text.splitlines(), 1):
            parts = line.split()
            if not parts or parts[0].startswith("c"):
                continue
            try:
                if parts[0] in {"a", "o", "t", "f"}:
                    if len(parts) not in (2, 3) or (len(parts) == 3 and parts[2] != "0"):
                        raise ValueError
                    node_id = int(parts[1])
                    if node_id <= 0:
                        raise ValueError
                    graph[node_id] = _D4Node(parts[0], edges.setdefault(node_id, []))
                else:
                    values = [int(part) for part in parts]
                    if len(values) < 3 or values[0] <= 0 or values[1] <= 0 or values[-1] != 0:
                        raise ValueError
                    if 0 in values[2:-1]:
                        raise ValueError
                    edges.setdefault(values[0], []).append((values[1], values[2:-1]))
            except ValueError as exc:
                raise ValueError(f"{line_number}: malformed serialized d4 record") from exc

        #  Walk reachable nodes in postorder
        visited: set[int] = set()
        visiting: set[int] = set()
        stack = [(1, False)]
        while stack:
            node_id, expanded = stack.pop()
            if node_id in visited:
                continue
            node = graph.get(node_id)
            if node is None:
                raise ValueError(f"Missing declaration for d4 node {node_id}")
            if expanded:
                visiting.remove(node_id)
                visited.add(node_id)
                yield node_id, node
            else:
                if node_id in visiting:
                    raise ValueError("Cycle in d4 circuit")
                visiting.add(node_id)
                stack.append((node_id, True))
                stack.extend((child, False) for child, _ in node.edges)

    def save(self, directory: Path) -> None:
        data = {"var_count": self.var_count, "remapping": {str(k): v for k, v in self.remapping.items()}}
        with saving_to(directory) as temporary_directory:
            temporary_directory.mkdir()
            (temporary_directory / "circuit.nnf").write_text(self.nnf_text)
            write_metadata(temporary_directory, "ddnnf", codec="d4", files=["circuit.nnf"], **data)

    @classmethod
    def load(cls, directory: Path) -> Self:
        directory = Path(directory)
        data = read_metadata(directory)
        remapping = {int(k): v for k, v in data["remapping"].items()}
        return cls((directory / "circuit.nnf").read_text(), data["var_count"], remapping)


class BCS12Walker(DagWalker):
    """Generate the BC-S1.2 encoding of the Boolean abstraction of a PySMT formula."""

    def __init__(self, abstractor: Abstractor, remapping: Mapping[int, int]) -> None:
        DagWalker.__init__(self, invalidate_memoization=True)
        self._abs = abstractor
        self._remapping = remapping
        self._gate_counter = 0
        self._gate_lines: list[str] = []

    @property
    def gate_lines(self) -> list[str]:
        return self._gate_lines

    def _map(self, formula: FNode) -> str:
        assert formula in self._abs, "Abstraction must be prepared"
        return f"v{self._remapping[self._abs.get_id(formula)]}"

    @staticmethod
    def _remove_double_neg(s: str) -> str:
        return s.replace("--", "")

    def walk_symbol(self, formula: FNode, args: tuple, **kwargs: object) -> str | None:
        if not formula.symbol_type().is_bool_type():
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
        return self._map(formula)

    def walk_and(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        assert None not in args
        self._gate_counter += 1
        gate = f"g{self._gate_counter}"
        self._gate_lines.append(f"G {gate} := A " + " ".join(set(args)))
        return gate

    def walk_or(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        assert None not in args
        self._gate_counter += 1
        gate = f"g{self._gate_counter}"
        self._gate_lines.append(f"G {gate} := O " + " ".join(set(args)))
        return gate

    def walk_not(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        assert None not in args
        return self._remove_double_neg(f"-{args[0]}")

    def walk_implies(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        assert None not in args
        self._gate_counter += 1
        gate = f"g{self._gate_counter}"
        line = f"G {gate} := O -{args[0]} {args[1]}"
        self._gate_lines.append(self._remove_double_neg(line))
        return gate

    def walk_iff(self, formula: FNode, args: tuple, **kwargs: object) -> str:
        assert None not in args
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
        assert None not in args
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
    """PropCompiler that compiles an SMT formula into a d-DNNF via d4v2."""

    def __init__(self, *, input_mode: Literal["circuit", "cnf"] = "circuit", options: Sequence[str] = ()) -> None:
        """Initialize the interface to the compiler.

        Args:
            input_mode: The input format fed to the compiler. d4v2 accepts either classic CNF input, or a non-CNF input
                in the BC-S1.2 circuit format.
            options: list of command line options to pass to the compiler.
        """
        if input_mode not in ("circuit", "cnf"):
            raise ValueError(f"Unsupported d4 input mode: {input_mode}")
        self.input_mode = input_mode
        self.options = tuple(options)

    @staticmethod
    def _write_cnf(
        formula: FNode,
        abstractor: Abstractor,
        remapping: Mapping[int, int],
        projected_ids: set[int],
        path: Path,
    ) -> None:
        atom_ids = {abstractor.get_atom(abstractor_id): d4_id for abstractor_id, d4_id in remapping.items()}
        clauses, variable_count = CNFConverter().convert(formula, atom_ids)
        if clauses == [[]]:
            # This d4 fork ignores empty clauses; contradictory units preserve false.
            clauses = [[1], [-1]]
            variable_count = max(variable_count, 1)
        with path.open("w") as f:
            ids = sorted(remapping[abstractor_id] for abstractor_id in projected_ids)
            f.write("c p show " + " ".join(map(str, [*ids, 0])) + "\n")
            f.write(f"p cnf {variable_count} {len(clauses)}\n")
            for clause in clauses:
                f.write(" ".join(map(str, [*clause, 0])) + "\n")

    @staticmethod
    def _write_circuit(
        formula: FNode,
        abstractor: Abstractor,
        remapping: Mapping[int, int],
        projected_ids: set[int],
        path: Path,
    ) -> None:
        walker = BCS12Walker(abstractor, remapping)
        root_gate = walker.translate(formula)

        with open(path, "w") as f:
            f.write("c BC-S1.2\n")
            for d4_id in remapping.values():
                f.write(f"I v{d4_id}\n")
            ids = sorted(remapping[aid] for aid in projected_ids)
            if ids:
                f.write("P " + " ".join(f"v{i}" for i in ids) + "\n")
            else:
                f.write("P\n")
            for line in walker.gate_lines:
                f.write(line + "\n")
            f.write(f"T {root_gate}\n")

    def _run_d4(self, circuit_path: Path, out_path: Path) -> None:
        cmd = [
            str(D4_BIN),
            "-i",
            str(circuit_path),
            "--input-type",
            self.input_mode,
            "--dump-file",
            str(out_path),
        ]
        if self.input_mode == "circuit" and not any(
            token == "--remove-gates" or token.startswith("--remove-gates=") for token in self.options
        ):
            # with circuit mode, by default enable the gate-removal option
            cmd.extend(["--remove-gates", "1"])
        cmd.extend(self.options)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"d4 compilation failed (exit {result.returncode}):\n{result.stderr.decode()}")

    def compile(
        self,
        phi: FNode,
        abstractor: Abstractor,
        *,
        all_atoms: Sequence[FNode],
        exists_atoms: Sequence[FNode] = (),
        forall_atoms: Sequence[FNode] = (),
        computation_logger: dict[str, object] | None = None,
    ) -> D4CompiledTarget:
        retained = compilation_vocabulary(phi, all_atoms, exists_atoms, forall_atoms)
        assert all(atom in abstractor for atom in all_atoms), "Abstraction must be prepared before compilation"
        if forall_atoms:
            raise NotImplementedError("d4 does not support universal variable elimination")
        stats = StatsCollector(computation_logger)
        with stats.track_time("compile_time"):
            atoms = list(all_atoms)
            if not atoms:
                if phi.is_true():
                    stats.log("n_atoms", 0)
                    stats.log("n_proj_vars", 0)
                    return D4CompiledTarget("t 1\n", 0)
                if phi.is_false():
                    stats.log("n_atoms", 0)
                    stats.log("n_proj_vars", 0)
                    return D4CompiledTarget("f 1\n", 0)

            with stats.track_time("register_atoms_time"):
                proj_set = set(retained)

            declared_atoms = set(all_atoms)
            all_atom_ids = sorted(abstractor.get_id(a) for a in all_atoms)

            projected_ids = {abstractor.get_id(a) for a in proj_set}
            # d4 assigns projected variables first; match that order before translation.
            ordered_ids = sorted(projected_ids) + [aid for aid in all_atom_ids if aid not in projected_ids]
            remapping = {abstractor_id: d4_id for d4_id, abstractor_id in enumerate(ordered_ids, 1)}

            with tempfile.TemporaryDirectory(prefix="d4_compile_") as tmpdir:
                tmp = Path(tmpdir)
                circuit_path = tmp / ("circuit.bc" if self.input_mode == "circuit" else "circuit.cnf")
                out_path = tmp / "output.nnf"

                writer = self._write_circuit if self.input_mode == "circuit" else self._write_cnf
                with stats.track_time(f"write_{self.input_mode}_time"):
                    writer(phi, abstractor, remapping, projected_ids, circuit_path)
                with stats.track_time("run_d4_time"):
                    self._run_d4(circuit_path, out_path)

                if len(projected_ids) == 0:
                    nnf_raw = out_path.read_text()
                    if nnf_raw.startswith("f"):
                        stats.log("n_atoms", len(declared_atoms))
                        stats.log("n_proj_vars", 0)
                        return D4CompiledTarget("f 1\n", 0, remapping=remapping)
                    stats.log("n_atoms", len(all_atoms))
                    stats.log("n_proj_vars", 0)
                    return D4CompiledTarget("t 1\n", 0, remapping=remapping)

                nnf_text = out_path.read_text()
                if nnf_text.startswith("f"):
                    stats.log("n_atoms", len(declared_atoms))
                    stats.log("n_proj_vars", len(projected_ids))
                    return D4CompiledTarget("f 1\n", 0, remapping=remapping)

            var_count = len(projected_ids)
            nnf_text = _clean_nnf(nnf_text, var_count)
            stats.log("n_atoms", len(all_atoms))
            stats.log("n_proj_vars", len(projected_ids))
            return D4CompiledTarget(nnf_text, var_count, remapping=remapping)
