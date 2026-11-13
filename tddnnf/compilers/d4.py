from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Self

import ddnnife
import pysmt.operators as op
from pysmt.fnode import FNode
from pysmt.formula import FormulaManager
from pysmt.walkers import DagWalker, handles

from tddnnf.core.abstraction import Abstractor
from tddnnf.core.interfaces import DagSize, PropCompiledTarget, PropCompiler
from tddnnf.core.persistence import read_metadata, saving_to, write_metadata
from tddnnf.core.pysmt_utils import compilation_vocabulary
from tddnnf.core.stats_collector import StatsCollector

D4_BIN = Path(__file__).resolve().parent.parent / "bin" / "d4.bin"


def _clean_nnf(nnf_text: str, var_count: int) -> str:
    """Remove nonprojected edge literals that d4 can leave despite the declared projection.

    This ensures the compiled circuit respects its projection universe.
    Projected variables occupy IDs 1..var_count; preserve nodes, edge endpoints,
    and terminating zeros, including edges emptied by filtering.
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
    edges: list[tuple[int, list[int]]] = field(default_factory=list)
    memo: FNode | None = None

    def to_pysmt(
        self,
        graph: dict[int, _D4Node],
        abstr: Abstractor,
        mgr: FormulaManager,
        inv_remap: dict[int, int],
    ) -> FNode:
        if self.memo is not None:
            return self.memo
        if self.node_type == "t":
            self.memo = mgr.TRUE()
        elif self.node_type == "f":
            self.memo = mgr.FALSE()
        elif self.node_type in ("o", "a"):
            children: list[FNode] = []
            for tgt, lits in self.edges:
                child = graph[tgt].to_pysmt(graph, abstr, mgr, inv_remap)
                if lits:
                    lit_assignments = [
                        abstr.get_atom(inv_remap[abs(lit)]) if lit > 0 else mgr.Not(abstr.get_atom(inv_remap[abs(lit)]))
                        for lit in lits
                    ]
                    children.append(mgr.And(child, *lit_assignments))
                else:
                    children.append(child)
            if self.node_type == "o":
                self.memo = mgr.Or(children) if children else mgr.FALSE()
            else:
                self.memo = mgr.And(children) if children else mgr.TRUE()
        assert self.memo is not None
        return self.memo


class D4CompiledTarget(PropCompiledTarget):
    """A compiled d-DNNF target backed by a d4 NNF file."""

    def __init__(self, nnf_text: str, var_count: int, remapping: Mapping[int, int] | None = None) -> None:
        self._nnf_text = nnf_text
        self._var_count = var_count
        self._remapping = MappingProxyType(dict(remapping) if remapping is not None else {})

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
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "circuit.nnf"
            path.write_text(self._nnf_text)
            ddnnf = ddnnife.Ddnnf.from_file(str(path), self._var_count)
        stats = ddnnf.statistics()
        return DagSize(vertices=stats.nodes.total, edges=stats.child_connections.total)

    def to_pysmt(self, abstr: Abstractor, mgr: FormulaManager) -> FNode:
        inv_remap = {v: k for k, v in self._remapping.items()}
        graph: dict[int, _D4Node] = {}

        for line in self._nnf_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts[0] in ("t", "f"):
                graph[int(parts[1])] = _D4Node(parts[0])
            elif parts[0] in ("o", "a"):
                graph[int(parts[1])] = _D4Node(parts[0])
            elif parts[-1] == "0":
                parts = parts[:-1]
                src = int(parts[0])
                tgt = int(parts[1])
                lits = [int(x) for x in parts[2:]]
                graph[src].edges.append((tgt, lits))

        return graph[1].to_pysmt(graph, abstr, mgr, inv_remap)

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
        assert formula in self._abs, "Abstraction must be prepared"
        return f"v{self._abs.get_id(formula)}"

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
    """PropCompiler that compiles an SMT formula into a d-DNNF via d4v2.

    The formula is first translated to BC-S1.2 circuit format, then compiled
    by the d4 binary. Edge literals are restricted to the dense projection IDs;
    metadata retains every projected dimension, including those absent from the DAG.
    This relies on the supported d4 circuit parser assigning sorted P variables first.
    """

    def _write_circuit(
        self,
        formula: FNode,
        abstractor: Abstractor,
        all_atom_ids: list[int],
        projected_ids: set[int],
        path: Path,
    ) -> None:
        walker = BCS12Walker(abstractor)
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

    def compile(
        self,
        formula: FNode,
        abstractor: Abstractor,
        *,
        all_vars: Sequence[FNode],
        exists_vars: Sequence[FNode] = (),
        forall_vars: Sequence[FNode] = (),
        computation_logger: dict[str, object] | None = None,
    ) -> D4CompiledTarget:
        retained = compilation_vocabulary(formula, all_vars, exists_vars, forall_vars)
        assert all(atom in abstractor for atom in all_vars), "Abstraction must be prepared before compilation"
        if forall_vars:
            raise NotImplementedError("d4 does not support universal variable elimination")
        stats = StatsCollector(computation_logger)
        with stats.track_time("compile_time"):
            atoms = list(all_vars)
            if not atoms:
                if formula.is_true():
                    stats.log("n_atoms", 0)
                    stats.log("n_proj_vars", 0)
                    return D4CompiledTarget("t 1\n", 0)
                if formula.is_false():
                    stats.log("n_atoms", 0)
                    stats.log("n_proj_vars", 0)
                    return D4CompiledTarget("f 1\n", 0)

            with stats.track_time("register_atoms_time"):
                proj_set = set(retained)

            all_atoms = set(all_vars)
            all_atom_ids = sorted(abstractor.get_id(a) for a in all_vars)

            projected_ids = {abstractor.get_id(a) for a in proj_set}

            with tempfile.TemporaryDirectory(prefix="d4_compile_") as tmpdir:
                tmp = Path(tmpdir)
                circuit_path = tmp / "circuit.bc"
                out_path = tmp / "output.nnf"

                with stats.track_time("write_circuit_time"):
                    self._write_circuit(formula, abstractor, all_atom_ids, projected_ids, circuit_path)
                with stats.track_time("run_d4_time"):
                    self._run_d4(circuit_path, out_path)

                if len(projected_ids) == 0:
                    nnf_raw = out_path.read_text()
                    if nnf_raw.startswith("f"):
                        stats.log("n_atoms", len(all_atoms))
                        stats.log("n_proj_vars", 0)
                        return D4CompiledTarget("f 1\n", 0, remapping={})
                    stats.log("n_atoms", len(all_atoms))
                    stats.log("n_proj_vars", 0)
                    return D4CompiledTarget("t 1\n", 0, remapping={})

                nnf_text = out_path.read_text()
                if nnf_text.startswith("f"):
                    stats.log("n_atoms", len(all_atoms))
                    stats.log("n_proj_vars", len(projected_ids))
                    return D4CompiledTarget("f 1\n", 0, remapping={})

            var_count = len(projected_ids)
            nnf_text = _clean_nnf(nnf_text, var_count)
            remapping = {aid: i + 1 for i, aid in enumerate(sorted(projected_ids))}
            stats.log("n_atoms", len(all_atoms))
            stats.log("n_proj_vars", len(projected_ids))
            return D4CompiledTarget(nnf_text, var_count, remapping=remapping)
