"""
Tests for Evaluation Benchmark Suite.
"""

import pytest
import os
from src.eval_harness import eval_harness


@pytest.mark.asyncio
async def test_evaluation_harness_execution():
    report = await eval_harness.run_all(run_adversarial=True)
    assert report.total_tests >= 10
    assert report.passed_tests > 0
    assert report.average_score >= 0.80, f"Expected average quality score >= 0.80, got {report.average_score}"
    assert os.path.exists("eval_report.json")
