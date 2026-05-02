"""Protocol adapter layer.

`build_adapter()` is the factory used by `MachineRegistry` to instantiate
the right adapter class for a given `MachineConfig.protocol_type`.
"""

from __future__ import annotations

from core.data_bus import MachineDataBus
from core.data_model import MachineConfig

from .base_adapter import BaseProtocolAdapter
from .opcua_adapter import OpcUaAdapter

__all__ = ["BaseProtocolAdapter", "OpcUaAdapter", "build_adapter"]


def build_adapter(config: MachineConfig, bus: MachineDataBus) -> BaseProtocolAdapter:
    """Factory: pick the adapter class matching `config.protocol_type`.

    Phase 1 supports only OPC-UA (real + simulator). Other protocols
    raise NotImplementedError until their adapters land.
    """
    proto = config.protocol.type.lower()
    if proto == "opcua":
        return OpcUaAdapter(config, bus)
    if proto in {"modbus_tcp", "modbus_rtu"}:
        raise NotImplementedError("Modbus adapter — TODO Phase 4")
    if proto == "ethernet_ip":
        raise NotImplementedError("EtherNet/IP adapter — TODO Phase 4")
    if proto == "ads":
        raise NotImplementedError("Beckhoff ADS adapter — TODO Phase 4")
    if proto == "mc_protocol":
        raise NotImplementedError("Mitsubishi MC adapter — TODO Phase 4")
    raise ValueError(f"Unknown protocol_type: {config.protocol.type!r}")
