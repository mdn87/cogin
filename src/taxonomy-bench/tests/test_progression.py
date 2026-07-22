from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from taxonomy_bench_progression import wilson_interval


def test_wilson_interval_handles_empty_and_known_samples():
    assert wilson_interval(0, 0) == (None, None)
    assert wilson_interval(8, 10) == pytest.approx((0.4902, 0.9433), abs=0.0001)
