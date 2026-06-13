# Architecture Specification: `tddnnf`

This document outlines the architecture, design principles, component interfaces,
and implementation plan for `tddnnf`, a Python library for Knowledge Compilation
Modulo Theories (KCMT).

---

## 1. Context & Objectives

Knowledge Compilation Modulo Theories (KCMT) compiles an SMT formula into a
target tractable representation (such as d-DNNF, SDD, or OBDD) using a
combination of theory lemmas and a classical propositional knowledge compiler.
Once compiled, demanding queries like model counting, satisfiability, and
clausal entailment can be executed in polynomial time relative to the size of
the compiled artifact.

### Core Architecture Goals

- **Backend Agnosticism:** Completely decouple syntax transformations from
  underlying propositional compilers (e.g., CLI tools like `d4`, or memory-bound
  Python libraries like `pysdd` and `cudd`).
- **Composability:** Rely on lightweight, single-responsibility components and
  Python Protocols rather than heavy, deeply nested inheritance hierarchies.
- **Semantic Soundness:** Guarantee correct mapping between SMT atomic
  predicates and Boolean variables throughout the compilation, querying, and
  serialization processes.
- **Interoperability:** Integrate directly with external lemma enumerators,
  specifically `tlemmas-enumeration`.

---

## 2. Core System Rules & Principles

Every component implemented in this repository must adhere to the following
architectural invariants:

### Rule 1: Structural SMT Normalization

SMT expressions can represent identical constraints via different syntactic
structures (e.g., $x \le y$ versus $y \ge x$). To prevent structural mismatches:

**All entry points must normalize expressions.** Both the input formula $\phi$,
the theory lemmas, and all subsequent queries must pass through a
`TheoryNormalizer` before entering the variable mapping layers.

### Rule 2: Vocabulary Constraints

- **Theory Lemmas** can introduce new atoms not present in the original formula
  $\phi$. The abstraction system must scale dynamically to assign new Boolean
  variables during compilation.
- **Queries** are structurally bound. They **cannot** introduce atoms that
  were not observed during the compilation phase. If a query introduces a
  completely novel atom, it cannot be mapped to the compiled circuit and must
  fail gracefully or evaluate to a trivial falsity.

### Rule 3: The Artifact-Context Duality (Persistence)

A compiled propositional graph (e.g., a `.nnf` file or an SDD node pointer)
is uninterpretable without its exact mapping context.

- The unit of disk serialization is never a raw circuit; it is a unified
  container (`TheoryCompiledTarget`) that packages the compiled target
  alongside its unique `AbstractionContext`.

---

## 3. Package Directory Layout

The codebase must strictly follow the modular layout below:

```text
tddnnf/
│
├── __init__.py
│
├── core/
│   ├── __init__.py
│   ├── abstraction.py       # Tracks SMT Atom <-> Bool Var mappings
│   ├── containers.py        # TheoryCompiledTarget unified wrapper
│   └── interfaces.py        # Python Protocols (PropCompiler, QueryEngine)
│
├── normalization/
│   ├── __init__.py
│   └── normalizer.py        # SMT canonicalization layer
│
├── builders/
│   ├── __init__.py
│   ├── reduced.py           # Implements T-Reduced syntax logic
│   └── extended.py          # Implements T-Extended syntax logic
│
├── compilers/
│   ├── __init__.py
│   ├── d4.py                # Wrapper for CLI d4 tool
│   ├── pysdd.py             # Adapter for PySDD
│   └── cudd.py              # Adapter for CUDD
│
└── queries/
    ├── __init__.py
    ├── d4_engine.py         # Query handler for d4 output (via ddnnfe)
    ├── sdd_engine.py        # Query handler for PySDD
    └── bdd_engine.py        # Query handler for CUDD
```

## 4. Key Interfaces & Types

To ensure type-safety and backend agnosticism across fundamentally different
compilers, we leverage Python typing generics and structural
subtyping (`Protocol`).

```python
from typing import Protocol, TypeVar
from pathlib import Path
from pysmt.fnode import FNode

# Protocol all compiled targets must implement
class PropCompiledTarget(Protocol):
    def save(self, directory: Path) -> None: ...
    @classmethod
    def load(cls, directory: Path) -> PropCompiledTarget: ...

T_Target = TypeVar("T_Target", bound=PropCompiledTarget)
T_Target_co = TypeVar("T_Target_co", bound=PropCompiledTarget, covariant=True)
```

### 4.1. Core Abstraction Mappings (core/abstraction.py)

Tracks the bidirectional state between normalized SMT atomic predicates and
propositional literal integers.

```python
class AbstractionContext:
    def __init__(self):
        self._smt_to_bool: dict[FNode, int] = {}
        self._bool_to_smt: dict[int, FNode] = {}

    def get_bool(self, smt_atom: Any) -> int:
        """Retrieves or registers a unique positive integer literal for an SMT atom."""
        if smt_atom not in self._smt_to_bool:
            idx = len(self._smt_to_bool) + 1
            self._smt_to_bool[smt_atom] = idx
            self._bool_to_smt[idx] = smt_atom
        return self._smt_to_bool[smt_atom]

    def get_smt(self, bool_var: int) -> Any:
        """Retrieves the SMT atom associated with a given boolean variable integer."""
        return self._bool_to_smt[abs(bool_var)]

    def abstract(self, smt_formula: Any) -> Any:
        """
        Recursively parses an SMT formula tree, converting atoms to
        propositional elements.
        """
        ...

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "AbstractionContext": ...
```

### 4.2. Unified Storage Container (core/containers.py)

Binds the compiled target and the abstraction context into an atomic, serialize-
safe object.

```python
class TheoryCompiledTarget(Generic[T_Target]):
    def __init__(self, target: T_Target, context: AbstractionContext):
        self.target: T_Target = target
        self.context: AbstractionContext = context

    def save(self, directory: Path) -> None:
        """Saves the context map and delegates target persistence to the
        backend via PropCompiledTarget.save()."""
        ...

    @classmethod
    def load(cls, directory: Path, target_type: type[T_Target]) -> "TheoryCompiledTarget[T_Target]":
        """Reconstructs a context instance and loads the target via
        PropCompiledTarget.load()."""
        ...
```

### 4.3. Functional Protocols (core/interfaces.py)

Defines the strict interfaces that third-party concrete classes must implement.

```python
class PropCompiler(Protocol[T_Target_co]):
    def compile(self, propositional_formula: Any) -> T_Target_co:  # covariant
        """Compiles a propositional structure into its target internal representation."""
        ...

class QueryEngine(Protocol[T_Target_co]):
    def __init__(self, compilation: "TheoryCompiledTarget[T_Target_co]", normalizer: Any):
      ...
    def is_satisfiable(self) -> bool: ...
    def model_count(self) -> int: ...
    def clause_entails(self, query_clause: Any) -> bool: ...
```

### 4.4. Compilation Strategies (builders/)

The builders implement syntax transformations. They remain oblivious to how the
backend compiler works underneath.

- T-reduced strategy: $\phi\wedge\bigwedge_{lemma\in Lemmas}{lemma}$
- T-extended strategy: $\phi\vee\bigvee_{lemma\in Lemmas^\prime}{\neg lemma}$

```python
class TReducedBuilder(Generic[T_Target]):
    def __init__(self, compiler: PropCompiler[T_Target]):
        self.compiler = compiler

    def build(self, phi: FNode, lemmas: List[FNode], context: AbstractionContext)
      -> TheoryCompiledTarget[T_Target]:
        # 1. Structural conjoin
        combined_smt = self._conjoin(phi, lemmas)
        # 2. Boolean map generation
        bool_formula = context.abstract(combined_smt)
        # 3. Prop compilation
        target = self.compiler.compile(bool_formula)
        return TheoryCompiledTarget(target, context)
```

## 5. Incremental Implementation Workflow (AI Instructions)

When implementing code with an AI assistant (like Opencode), use the following
sequential phases to maintain strict context isolation and prevent code
regression:

### Phase 1 (Directory Generation)

Instruct the tool to output bash commands to create the folder hierarchy and
empty files. Do not generate code logic during this step.

### Phase 2 (Core Specifications)

Implement core/interfaces.py, core/abstraction.py, and
normalization/normalizer.py.
Validate these with simple unit tests showing SMT to propositional round-trips.

### Phase 3 (The T-Builders)

Write builders/reduced.py and builders/extended.py.
Test them using a mock compiler class that satisfies the PropCompiler protocol

### Phase 4 (Isolated Backend Sprints)

Dedicate isolated chat sessions to specific compilers (e.g., implementing
compilers/d4.py and queries/d4_engine.py together).
Wipe chat history before starting a different backend like PySDD to keep the
context clean

```

```
