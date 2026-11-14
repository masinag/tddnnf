from collections.abc import Iterator

import pytest
from pysmt.environment import Environment


@pytest.fixture
def env() -> Iterator[Environment]:
    with Environment() as environment:
        yield environment
