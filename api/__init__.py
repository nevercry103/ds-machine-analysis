"""DS Machine Analyzer — API layer.

FastAPI-based async HTTP + WebSocket gateway. The API is the **spine** of
the platform: PyQt6 desktop, PWA web HMI, CLI tools, 3rd-party MES
integrations all consume the same endpoints. Core business logic lives in
`core/`; this layer only handles transport, auth, and serialization.

Design rules:
- API never imports from `ui/` (UI consumes API, not the other way around)
- All endpoints are async (`async def`) — backend is asyncio-native
- Pydantic schemas in `api/schemas/` are the wire format; never expose
  internal `core/data_model.py` dataclasses directly
- WebSocket = live events (cycle complete, NG, alarm), HTTP = queries
- Auth via JWT scopes (operator / engineer / manager / executive) —
  same API, different filtered responses per scope
"""
