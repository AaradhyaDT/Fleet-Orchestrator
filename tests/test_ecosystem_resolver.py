"""Tests for Canonical Ecosystem Name Mapping and Resolver Engine."""

from pathlib import Path
from tools.ecosystem_resolver import EcosystemResolver


def test_resolve_exact_canonical():
    resolver = EcosystemResolver()
    target = resolver.resolve("fleet-orchestrator")
    assert target is not None
    assert target.canonical_name == "fleet-orchestrator"
    assert "Fleet-Orchestrator" in str(target.local_path)
    assert target.azmuth_universe == "u0_ecosystem_mesh"


def test_resolve_aliases_spark():
    resolver = EcosystemResolver()
    for query in ["SPARK", "spark-edge", "spark", "spark_wearable"]:
        target = resolver.resolve(query)
        assert target is not None
        assert target.canonical_name == "spark"
        assert target.local_path.name == "SPARK"
        assert target.azmuth_universe == "u10_spark_edge_ai_telemetry"


def test_resolve_aliases_bias_aperture():
    resolver = EcosystemResolver()
    for query in ["biasaperture", "BiasAperture", "bias_aperture", "bias-aperture"]:
        target = resolver.resolve(query)
        assert target is not None
        assert target.canonical_name == "bias-aperture"
        assert target.local_path.name == "BiasAperture"
        assert target.azmuth_universe == "u11_bias_aperture_vision_audit"


def test_resolve_cyber_forensics():
    resolver = EcosystemResolver()
    target = resolver.resolve("forensics")
    assert target is not None
    assert target.canonical_name == "cyber-forensics"
    assert target.local_path.name == "Cyber-Forensics"


def test_resolve_subfolder_spaces():
    resolver = EcosystemResolver()
    target = resolver.resolve("fusion360-mcp")
    assert target is not None
    assert "AEC-MCP Suite" in str(target.local_path)
    assert target.azmuth_universe == "u5_hardware_physics_bom"


def test_list_all_targets():
    resolver = EcosystemResolver()
    targets = resolver.list_all_targets()
    assert len(targets) >= 12
    canonicals = [t.canonical_name for t in targets]
    assert "fleet-orchestrator" in canonicals
    assert "spark" in canonicals
    assert "bias-aperture" in canonicals
    assert "problem-dissector" in canonicals
