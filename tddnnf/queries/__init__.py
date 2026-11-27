from typing import TYPE_CHECKING

from tddnnf.queries.cudd_engine import CuddEngine
from tddnnf.queries.ddnnife_engine import DdnnifeEngine
from tddnnf.queries.pysdd_engine import PySddEngine
from tddnnf.queries.query_session import QuerySession

if TYPE_CHECKING:
    from tddnnf.queries.decdnnf_rs_engine import DecDnnfRsEngine

__all__ = ["CuddEngine", "DdnnifeEngine", "DecDnnfRsEngine", "PySddEngine", "QuerySession"]


def __getattr__(name: str) -> object:
    if name == "DecDnnfRsEngine":
        try:
            from tddnnf.queries.decdnnf_rs_engine import DecDnnfRsEngine
        except ModuleNotFoundError as exc:
            if exc.name == "decdnnf_rs_py":
                raise ImportError(
                    "DecDnnfRsEngine requires the optional 'decdnnf' extra; "
                    "install it with `pip install 'tddnnf[decdnnf]'`."
                ) from exc
            raise
        return DecDnnfRsEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
