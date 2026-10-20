"""tests/test_opportunity_harvester.py
------------------------------------
Unit tests for the Sovereign & Multilateral Opportunity Harvester.
"""

from pathlib import Path
import pytest

from tools.harvest_sovereign_opportunities import (
    SovereignOpportunityHarvester,
    OpportunityRecord,
    GOLDEN_OPPORTUNITIES,
)


@pytest.fixture
def temp_opportunities_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "opportunities"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def test_harvester_golden_seed_load(temp_opportunities_dir: Path):
    """Verifies that golden seeds are indexed and structured properly."""
    harvester = SovereignOpportunityHarvester(output_dir=temp_opportunities_dir)
    records = harvester.harvest(source_filter="all", limit=4)
    assert len(records) == 4
    for r in records:
        assert isinstance(r, OpportunityRecord)
        assert r.id
        assert r.title
        assert r.organization
        assert r.tax_status in ("TAX_FREE", "UN_EXEMPT", "LOCAL_TAX")
        assert r.visa_pathway in ("UAE_GOLDEN_VISA", "UN_G4_DIPLOMATIC", "EMPLOYER_SPONSORED")


def test_harvester_gcc_filter(temp_opportunities_dir: Path):
    """Verifies filtering by gcc sovereign sector."""
    harvester = SovereignOpportunityHarvester(output_dir=temp_opportunities_dir)
    records = harvester.harvest(source_filter="gcc")
    assert len(records) > 0
    for r in records:
        assert r.category == "SOVEREIGN_GCC"
        assert r.tax_status == "TAX_FREE"
        assert r.visa_pathway == "UAE_GOLDEN_VISA"


def test_harvester_un_filter(temp_opportunities_dir: Path):
    """Verifies filtering by un multilateral sector."""
    harvester = SovereignOpportunityHarvester(output_dir=temp_opportunities_dir)
    records = harvester.harvest(source_filter="un")
    assert len(records) > 0
    for r in records:
        assert r.category == "UN_MULTILATERAL"
        assert r.tax_status == "UN_EXEMPT"
        assert r.visa_pathway == "UN_G4_DIPLOMATIC"


def test_harvester_catalog_files_written(temp_opportunities_dir: Path):
    """Verifies catalog.json, summary.json, and individual record files."""
    harvester = SovereignOpportunityHarvester(output_dir=temp_opportunities_dir)
    records = harvester.harvest(limit=2)
    assert harvester.catalog_path.exists()
    assert harvester.summary_path.exists()
    for r in records:
        rec_file = harvester.records_dir / f"{r.id}.json"
        assert rec_file.exists()
