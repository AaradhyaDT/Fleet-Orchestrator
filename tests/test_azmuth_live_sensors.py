"""Tests for Live Hardware & Telemetry Ingestion."""

from pathlib import Path
from tools.azmuth_live_sensors import AzmuthLiveSensors


def test_read_hardware_snapshot():
    collector = AzmuthLiveSensors()
    snapshot = collector.read_hardware_snapshot()

    assert snapshot.cpu_load_pct >= 0.0
    assert snapshot.ram_saturation_pct >= 0.0
    assert snapshot.cpu_package_temp_c > 0.0
    assert snapshot.estimated_power_mw > 0.0
    assert snapshot.spark_imu_rate_hz == 200.0
    assert snapshot.spark_freertos_watermark > 0


def test_update_universes_cache(tmp_path: Path):
    collector = AzmuthLiveSensors(state_dir=tmp_path)
    cache = collector.update_universes_cache()

    assert "mapped_universe_nodes" in cache
    mapped = cache["mapped_universe_nodes"]
    assert "u6_energy_thermal_power::HOST_CPU_PACKAGE_TEMP_C" in mapped
    assert "u10_spark_edge_ai_telemetry::IMU_RAW_JERK_SAMPLE_RATE_HZ" in mapped
    assert (tmp_path / "azmuth_sensor_cache.json").exists()
