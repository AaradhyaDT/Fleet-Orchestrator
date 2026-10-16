#!/usr/bin/env python3
"""tests/test_ultimatrix_solver.py
--------------------------------
Unit tests for the Azmuth Ultimatrix Autonomous Solver and Verifier.
"""

from pathlib import Path
from tools.ultimatrix_solver import (
    extract_samples_from_html,
    extract_samples_from_markdown,
    get_task_samples,
    execute_python_solution,
    verify_task_solution,
)


def test_extract_samples_from_markdown():
    sample_md = """
# Sample Task

| Input | Output |
| --- | --- |
| 10 20 | 30 |
| 5 7 | 12 |
"""
    samples = extract_samples_from_markdown(sample_md)
    assert len(samples) == 2
    assert samples[0] == ("10 20", "30")
    assert samples[1] == ("5 7", "12")


def test_extract_samples_from_html():
    sample_html = """
<div class="challenge">
<pre>3
1 2 3</pre>
<pre>6</pre>
</div>
"""
    samples = extract_samples_from_html(sample_html)
    assert len(samples) == 1
    assert samples[0] == ("3\n1 2 3", "6")


def test_execute_python_solution_sandbox():
    code = """
import sys
a, b = map(int, sys.stdin.read().split())
print(a + b)
"""
    code_ret, out, err = execute_python_solution(code, "15 25")
    assert code_ret == 0
    assert out.strip() == "40"
    assert err == ""


def test_verify_known_sample_pass():
    from tools.ultimatrix_solver import HACKERRANK_TASKS
    task_dir = HACKERRANK_TASKS / "akritis-one-and-two"
    sub_path = task_dir / "submissions" / "1416433326_1pts.py"
    if task_dir.exists() and sub_path.exists():
        res = get_task_samples("akritis-one-and-two")
        assert len(res) >= 1
        v = verify_task_solution("akritis-one-and-two", sub_path)
        assert v["status"] == "PASSED"
        assert v["all_passed"] is True
    else:
        # Synthetic test for CI environments without local disk clone of Competitive-Programming
        sample_html = """
<div class="challenge">
<pre>1 2
3 4</pre>
<pre>7</pre>
</div>
"""
        samples = extract_samples_from_html(sample_html)
        assert len(samples) == 1
        assert samples[0] == ("1 2\n3 4", "7")
