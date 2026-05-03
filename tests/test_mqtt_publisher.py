"""MQTT publisher tests — unit tests without a real broker."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.data_model import DataBusEvent
from core.mqtt_publisher import MqttConfig, MqttPublisher


def test_mqtt_config_defaults():
    cfg = MqttConfig()
    assert cfg.enabled is False
    assert cfg.broker == "localhost"
    assert cfg.port == 1883
    assert cfg.topic_prefix == "ds-ma"


def test_topic_generation():
    pub = MqttPublisher(MqttConfig())
    assert pub._topic_for("m1", "cycle_summary") == "ds-ma/m1/cycle"
    assert pub._topic_for("m1", "cycle_anomaly") == "ds-ma/m1/anomaly"
    assert pub._topic_for("m1", "alarm") == "ds-ma/m1/alarm"
    assert pub._topic_for("m1", "status_change") == "ds-ma/m1/status"
    assert pub._topic_for("m1", "downtime_tag") == "ds-ma/m1/downtime"


def test_custom_prefix():
    pub = MqttPublisher(MqttConfig(topic_prefix="factory/line1"))
    assert pub._topic_for("m1", "cycle_summary") == "factory/line1/m1/cycle"


def test_serialize_event():
    event = DataBusEvent(
        machine_id="m1",
        event_type="cycle_summary",
        timestamp=datetime(2026, 5, 3, 10, 0, 0, tzinfo=timezone.utc),
        payload={"total_ms": 5000, "steps": 5},
    )
    json_str = MqttPublisher._serialize(event)
    assert '"machine_id": "m1"' in json_str
    assert '"type": "cycle_summary"' in json_str
    assert '"total_ms": 5000' in json_str


@pytest.mark.asyncio
async def test_publish_noop_when_disabled():
    """When disabled, publish_event is a silent no-op."""
    pub = MqttPublisher(MqttConfig(enabled=False))
    event = DataBusEvent(
        machine_id="m1",
        event_type="cycle_summary",
        timestamp=datetime(2026, 5, 3, 10, 0, 0, tzinfo=timezone.utc),
    )
    await pub.publish_event(event)  # no exception, no broker needed


@pytest.mark.asyncio
async def test_publish_filters_unknown_event_types():
    """Events not in the publish list are silently dropped."""
    pub = MqttPublisher(MqttConfig(enabled=True))
    # _connected is False, but the filter happens before the connection check
    event = DataBusEvent(
        machine_id="m1",
        event_type="unknown_type",
        timestamp=datetime(2026, 5, 3, 10, 0, 0, tzinfo=timezone.utc),
    )
    await pub.publish_event(event)  # no exception
