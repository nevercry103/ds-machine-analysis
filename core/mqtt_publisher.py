"""MQTT event publisher — publishes cycle/alarm/anomaly events to a broker.

Enables MES/SCADA/Historian integration (F-006 competitive gap vs
Beckhoff TwinCAT Analytics and Siemens Insights Hub). Subscribes to
the per-machine Data Bus and forwards selected event types as JSON
payloads to configurable MQTT topics.

Topic layout (convention):
    ds-ma/{machine_id}/cycle
    ds-ma/{machine_id}/alarm
    ds-ma/{machine_id}/anomaly
    ds-ma/{machine_id}/status
    ds-ma/{machine_id}/downtime

Requires `aiomqtt` (paho-mqtt async wrapper). When the broker is
unreachable, events are silently dropped with a warning — the platform
must never block on a downstream consumer.

Architecture layer: CORE (integration)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime

from utils.logger import log

# Event types forwarded to MQTT — mirrors _BROADCAST_EVENT_TYPES in api/main.py.
_PUBLISH_EVENT_TYPES = {"cycle_summary", "cycle_anomaly", "alarm", "status_change", "downtime_tag"}


@dataclass
class MqttConfig:
    """MQTT broker connection settings."""

    enabled: bool = False
    broker: str = "localhost"
    port: int = 1883
    topic_prefix: str = "ds-ma"
    username: str = ""
    password: str = ""
    client_id: str = "ds-machine-analyzer"
    qos: int = 1


class MqttPublisher:
    """Publishes Data Bus events to an MQTT broker.

    Usage:
        publisher = MqttPublisher(config)
        await publisher.start()
        # ... wire as bus subscriber ...
        await publisher.stop()

    When `aiomqtt` is not installed or the broker is unreachable, the
    publisher logs a warning and drops events — never blocks the bus.
    """

    def __init__(self, config: MqttConfig) -> None:
        self._config = config
        self._client = None
        self._connected = False

    async def start(self) -> None:
        """Connect to the broker. No-op when MQTT is disabled."""
        if not self._config.enabled:
            log.info("MQTT publisher disabled (mqtt.enabled=false)")
            return
        try:
            import aiomqtt  # noqa: F401 — availability check
        except ImportError:
            log.warning(
                "aiomqtt not installed — MQTT publishing disabled. "
                "Install with: pip install aiomqtt"
            )
            return
        try:
            import aiomqtt

            self._client = aiomqtt.Client(
                hostname=self._config.broker,
                port=self._config.port,
                username=self._config.username or None,
                password=self._config.password or None,
                identifier=self._config.client_id,
            )
            await self._client.__aenter__()
            self._connected = True
            log.info(
                "MQTT connected",
                broker=self._config.broker,
                port=self._config.port,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("MQTT connection failed", error=str(exc))
            self._client = None
            self._connected = False

    async def stop(self) -> None:
        """Disconnect from the broker."""
        if self._client is not None and self._connected:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._connected = False
            self._client = None
            log.info("MQTT disconnected")

    async def publish_event(self, event) -> None:
        """Publish a DataBusEvent to MQTT. Silently drops on failure."""
        if not self._connected or self._client is None:
            return
        if event.event_type not in _PUBLISH_EVENT_TYPES:
            return

        topic = self._topic_for(event.machine_id, event.event_type)
        payload = self._serialize(event)

        try:
            await self._client.publish(
                topic,
                payload=payload.encode("utf-8"),
                qos=self._config.qos,
            )
            log.debug("MQTT published", topic=topic)
        except Exception as exc:  # noqa: BLE001
            log.warning("MQTT publish failed", topic=topic, error=str(exc))

    def _topic_for(self, machine_id: str, event_type: str) -> str:
        """Build the MQTT topic from prefix + machine_id + event category."""
        # Map event_type to a clean topic suffix
        suffix_map = {
            "cycle_summary": "cycle",
            "cycle_anomaly": "anomaly",
            "alarm": "alarm",
            "status_change": "status",
            "downtime_tag": "downtime",
        }
        suffix = suffix_map.get(event_type, event_type)
        return f"{self._config.topic_prefix}/{machine_id}/{suffix}"

    @staticmethod
    def _serialize(event) -> str:
        """Serialize a DataBusEvent to JSON."""

        def _default(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)

        return json.dumps(
            {
                "machine_id": event.machine_id,
                "type": event.event_type,
                "timestamp": event.timestamp.isoformat()
                if isinstance(event.timestamp, datetime)
                else str(event.timestamp),
                "payload": event.payload,
            },
            default=_default,
        )


def make_mqtt_forwarder(publisher: MqttPublisher):
    """Create a Data Bus subscriber callback that forwards events to MQTT."""

    async def forwarder(event) -> None:
        await publisher.publish_event(event)

    return forwarder
