import json
import pytest
from tools.harvest_task_time_dataset import (
    clean_prompt_text,
    assign_time_tier,
    assign_execution_route,
    calculate_cpm_weight,
    calculate_timeout_ceiling,
    format_training_example,
)


def test_clean_prompt_text():
    raw = """<USER_REQUEST>
Fix the regression in test_warehouse_mem_sim.py
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-10-09T20:28:13+05:45.
</ADDITIONAL_METADATA>
<USER_SETTINGS_CHANGE>
The user changed setting Model Selection.
</USER_SETTINGS_CHANGE>"""
    cleaned = clean_prompt_text(raw)
    assert cleaned == "Fix the regression in test_warehouse_mem_sim.py"
    assert "<USER_REQUEST>" not in cleaned
    assert "ADDITIONAL_METADATA" not in cleaned


def test_assign_time_tier():
    assert assign_time_tier(5.0) == "T0_MICRO"
    assert assign_time_tier(30.0) == "T1_FAST"
    assert assign_time_tier(100.0) == "T2_MEDIUM"
    assert assign_time_tier(300.0) == "T3_LONG"
    assert assign_time_tier(600.0) == "T4_EPIC"


def test_calculate_timeout_ceiling():
    assert calculate_timeout_ceiling(10.0) == 30
    assert calculate_timeout_ceiling(45.0) == 99
    assert calculate_timeout_ceiling(1000.0) == 1200


def test_calculate_cpm_weight():
    assert calculate_cpm_weight(15.0) == 0.5
    assert calculate_cpm_weight(60.0) == 2.0
    assert calculate_cpm_weight(120.0) == 4.0


def test_format_training_example():
    sample = {
        "prompt": "Scaffold IOE semester IV-II notes for CE 752",
        "duration_s": 80.0,
        "tool_count": 5,
        "source": "antigravity_transcript",
    }
    formatted = format_training_example(sample)
    assert "instruction" in formatted
    assert "input" in formatted
    assert "output" in formatted
    
    payload = json.loads(formatted["output"])
    assert payload["archetype"] == "RESEARCH_ACADEMIC"
    assert "time_allocation" in payload
    ta = payload["time_allocation"]
    assert "tier" in ta
    assert "estimated_duration_s" in ta
    assert "timeout_ceiling_s" in ta
    assert "cpm_weight" in ta
    assert "execution_route" in ta
