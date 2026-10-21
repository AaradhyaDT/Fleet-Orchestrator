import pytest
from tools.azmuth_notifier import notify_opportunity
from tools.azmuth_ats_sensor import score_role_salience, fetch_ashby_jobs

def test_score_role_salience():
    job1 = {"title": "Research Engineer, Kernel Optimization (CUDA)", "department": "Inference Systems"}
    assert score_role_salience(job1) >= 3.0

    job2 = {"title": "Office Administrator", "department": "People Ops"}
    assert score_role_salience(job2) == 0.0

def test_notifier_dedup():
    test_id = "test_unit_dedup_item_123"
    # First notification should succeed
    res1 = notify_opportunity("Test Title", "Test Message", item_id=test_id, force=False)
    assert res1 is True

    # Second notification should be suppressed
    res2 = notify_opportunity("Test Title", "Test Message", item_id=test_id, force=False)
    assert res2 is False
