"""WebSocket endpoints — live cycle / event / alarm streaming.

Each client connects to `/ws/machines/{machine_id}/events`. The server
hands the client an `asyncio.Queue` registered with `WSHub`. Every event
the data bus forwards to the hub is pushed to all client queues for that
machine.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.state import AppState
from utils.logger import log

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/machines/{machine_id}/events")
async def machine_events(websocket: WebSocket, machine_id: str) -> None:
    state: AppState | None = getattr(websocket.app.state, "app_state", None)
    if state is None:
        await websocket.close(code=1011, reason="App state not ready")
        return

    handle = state.registry.get(machine_id)
    if handle is None:
        await websocket.close(code=1008, reason=f"Unknown machine {machine_id}")
        return

    await websocket.accept()
    queue = state.ws_hub.add_client(machine_id)
    log.info("WebSocket client connected", machine_id=machine_id)

    try:
        # Send initial state so the client doesn't render an empty card.
        await websocket.send_json(
            {
                "type": "status_change",
                "machine_id": machine_id,
                "payload": {
                    "status": handle.status.value,
                    "last_cycle_ms": int(handle.processor.last_total_ms)
                    if handle.processor.last_total_ms
                    else None,
                    "cycle_count": handle.processor.cycle_count,
                },
            }
        )

        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        log.info("WebSocket client disconnected", machine_id=machine_id)
    except Exception as exc:
        log.exception(
            "WebSocket error", machine_id=machine_id, error=str(exc)
        )
    finally:
        state.ws_hub.remove_client(machine_id, queue)
