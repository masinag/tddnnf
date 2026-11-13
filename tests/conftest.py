from collections.abc import Callable, Iterator

import pytest
from pysmt.environment import Environment
from pysmt.fnode import FNode


@pytest.fixture
def env() -> Iterator[Environment]:
    with Environment() as environment:
        yield environment


@pytest.fixture
def assert_owned_dag() -> Callable[[FNode, Environment], None]:
    def check(formula: FNode, environment: Environment) -> None:
        pending = [formula]
        seen = set()
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            assert node in environment.formula_manager
            seen.add(node)
            pending.extend(node.args())

    return check
