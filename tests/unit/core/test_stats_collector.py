import pytest

from tddnnf.core.stats_collector import StatsCollector


def test_without_logger_executes_timed_body() -> None:
    collector = StatsCollector()
    collector.log("value", 7)
    executed = False

    with collector.track_time("elapsed"):
        executed = True

    assert executed


def test_log_inserts_and_replaces_values() -> None:
    logger = {"unrelated": "keep", "value": 1}
    collector = StatsCollector(logger)

    collector.log("new", 7)
    assert logger == {"unrelated": "keep", "value": 1, "new": 7}

    collector.log("value", 2)
    assert logger == {"unrelated": "keep", "value": 2, "new": 7}


def test_timing_records_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([1_000_000_000, 1_250_000_000])

    def clock() -> int:
        return next(times)

    monkeypatch.setattr("tddnnf.core.stats_collector.time.perf_counter_ns", clock)
    logger = {}
    collector = StatsCollector(logger)

    with collector.track_time("elapsed"):
        pass

    assert logger == {"elapsed": 0.25}


def test_successive_timings_accumulate(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([1_000_000_000, 1_250_000_000, 2_000_000_000, 2_500_000_000])

    def clock() -> int:
        return next(times)

    monkeypatch.setattr("tddnnf.core.stats_collector.time.perf_counter_ns", clock)
    logger = {}
    collector = StatsCollector(logger)

    with collector.track_time("elapsed"):
        pass
    assert logger == {"elapsed": 0.25}

    with collector.track_time("elapsed"):
        pass
    assert logger == {"elapsed": 0.75}


def test_failed_timing_records_seconds_and_propagates_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([1_000_000_000, 1_250_000_000])

    def clock() -> int:
        return next(times)

    monkeypatch.setattr("tddnnf.core.stats_collector.time.perf_counter_ns", clock)
    logger = {}
    collector = StatsCollector(logger)
    error = RuntimeError("timed body failed")

    with pytest.raises(RuntimeError) as caught:
        with collector.track_time("elapsed"):
            raise error

    assert caught.value is error
    assert logger == {"elapsed": 0.25}
