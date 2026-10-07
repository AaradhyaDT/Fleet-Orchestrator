from __future__ import annotations

import pytest

from client.qa_verdict import DEFAULT_REVISION_REASON, parse_qa_verdict


def test_marker_pass():
    assert parse_qa_verdict("All good.\nQA_VERDICT: PASS") == ("pass", None)


def test_marker_revise_with_inline_reason():
    v, r = parse_qa_verdict("QA_VERDICT: REVISE - missing edge-case tests")
    assert v == "revision_needed"
    assert r == "missing edge-case tests"


def test_marker_revise_reason_on_following_lines():
    v, r = parse_qa_verdict("QA_VERDICT: REVISE\n\nLock is never released on error.\nAdd test.")
    assert v == "revision_needed"
    assert r == "Lock is never released on error.\nAdd test."


def test_marker_revise_without_reason_uses_default():
    assert parse_qa_verdict("QA_VERDICT: REVISE") == ("revision_needed", DEFAULT_REVISION_REASON)


def test_pass_text_mentioning_fail_still_passes():
    text = "Checked: no test fails, no failure paths unhandled, nothing to revise.\nQA_VERDICT: PASS"
    assert parse_qa_verdict(text) == ("pass", None)


def test_pass_text_mentioning_revision_needed_still_passes():
    text = "Earlier draft was revision_needed; now resolved.\nQA_VERDICT: PASS"
    assert parse_qa_verdict(text) == ("pass", None)


def test_revise_text_without_fail_keyword_is_revision():
    v, _ = parse_qa_verdict("Looks incomplete.\nQA_VERDICT: REVISE")
    assert v == "revision_needed"


def test_last_marker_wins_revise_then_pass():
    assert parse_qa_verdict("QA_VERDICT: REVISE\nfixed\nQA_VERDICT: PASS") == ("pass", None)


def test_last_marker_wins_pass_then_revise():
    v, r = parse_qa_verdict("QA_VERDICT: PASS\nwait, regression found\nQA_VERDICT: REVISE regression in X")
    assert (v, r) == ("revision_needed", "regression in X")


@pytest.mark.parametrize(
    "text",
    ["**QA_VERDICT: PASS**", "`QA_VERDICT: PASS`", "qa_verdict: pass", "QA_VERDICT :   Pass", "**QA_VERDICT:** PASS"],
)
def test_marker_formatting_tolerated(text):
    assert parse_qa_verdict(text) == ("pass", None)


def test_marker_requires_word_boundary():
    # "REVISED" / "PASSED" are not valid marker values -> falls back to legacy heuristic (no keywords => pass)
    assert parse_qa_verdict("QA_VERDICT: PASSED")[0] == "pass"
    v, _ = parse_qa_verdict("QA_VERDICT: REVISED but fail")
    assert v == "revision_needed"  # legacy fallback via 'fail'


def test_legacy_fail_keyword():
    assert parse_qa_verdict("Tests FAIL on edge case") == ("revision_needed", DEFAULT_REVISION_REASON)


def test_legacy_revision_needed_keyword():
    assert parse_qa_verdict("verdict: revision_needed") == ("revision_needed", DEFAULT_REVISION_REASON)


def test_legacy_no_keywords_passes():
    assert parse_qa_verdict("Looks great, ship it.") == ("pass", None)


def test_legacy_empty_and_none():
    assert parse_qa_verdict("") == ("pass", None)
    assert parse_qa_verdict(None) == ("pass", None)  # type: ignore[arg-type]


def test_reason_truncated():
    v, r = parse_qa_verdict("QA_VERDICT: REVISE " + "x" * 2000)
    assert v == "revision_needed" and len(r) == 500
