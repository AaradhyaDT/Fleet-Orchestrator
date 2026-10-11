import pytest
from client.local_llm import extract_json, is_online


def test_extract_json_direct():
    text = '{"archetype": "ENGINEERING_DEV", "matrix_cell": "(V0, R0)"}'
    parsed = extract_json(text)
    assert parsed is not None
    assert parsed["archetype"] == "ENGINEERING_DEV"


def test_extract_json_markdown_fenced():
    text = """```json
    {
        "archetype": "RESEARCH_ACADEMIC",
        "time_allocation": {"tier": "T2_MEDIUM"}
    }
    ```"""
    parsed = extract_json(text)
    assert parsed is not None
    assert parsed["archetype"] == "RESEARCH_ACADEMIC"
    assert parsed["time_allocation"]["tier"] == "T2_MEDIUM"


def test_extract_json_with_preceding_prose():
    text = """Here is your classification in strict JSON format:
    {"archetype": "FRONTEND_PRODUCT", "policy": "SURGICAL_LOCK"}
    Hope this helps!"""
    parsed = extract_json(text)
    assert parsed is not None
    assert parsed["archetype"] == "FRONTEND_PRODUCT"
    assert parsed["policy"] == "SURGICAL_LOCK"


def test_extract_json_invalid():
    assert extract_json("Not a json string at all") is None
    assert extract_json("") is None
    assert extract_json(None) is None


def test_is_online_closed_port():
    # An improbable local port to guarantee connection refusal
    assert is_online(host="127.0.0.1", port=59999, timeout=0.02) is False
