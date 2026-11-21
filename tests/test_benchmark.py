from benchmark.generate import columns
from benchmark.run_benchmark import score, table


def test_generator_is_seeded() -> None:
    assert columns(1, 20, 50) == columns(1, 20, 50)
    assert columns(1, 20, 50) != columns(2, 20, 50)


def test_small_benchmark_run() -> None:
    s = score(3, 100, 100, 1000)
    assert s.right / s.cols > 0.95
    assert s.rejected == 5 and s.loaded == 995
    assert "rows/sec" in table(s)
