"""WebSocket client thread for the PyQt6 desktop UI.

Connects to ``/ws/machines/{id}/events`` and emits Qt signals on
incoming events. Runs in a ``QThread`` with its own asyncio loop so
it never blocks the Qt main thread.

Replaces the 2-second polling that the Gantt widget used in Phase 1.
The machine list still polls (there is no WS endpoint for the full
list), but the selected machine's Gantt + KPI update in real time.

Architecture rule: UI talks to the server only via the API / WS
endpoints — no direct core/storage/bus imports.
"""

from __future__ import annotations

import asyncio
import json

from PyQt6.QtCore import QThread, pyqtSignal

from utils.logger import log


class MachineWSClient(QThread):
    """One WS subscription per selected machine.

    Signals
    -------
    eventReceived(dict)
        Raw JSON message from the server (``type``, ``machine_id``,
        ``timestamp``, ``payload``).
    connected()
        Emitted after the WS handshake succeeds.
    disconnected()
        Emitted when the connection drops (will auto-reconnect).
    """

    eventReceived = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    RECONNECT_DELAY_S = 3.0

    def __init__(
        self,
        base_url: str,
        machine_id: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        # Convert http(s) to ws(s)
        ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
        self._url = f"{ws_base.rstrip('/')}/ws/machines/{machine_id}/events"
        self._machine_id = machine_id
        self._running = True

    def run(self) -> None:
        """QThread entry — create a private asyncio loop and run the WS."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._ws_loop())
        except Exception as exc:
            log.warning("WS thread exiting", machine_id=self._machine_id, error=str(exc))
        finally:
            loop.close()

    async def _ws_loop(self) -> None:
        try:
            import websockets
        except ImportError:
            log.error("websockets package not installed — desktop WS client disabled")
            return

        while self._running:
            try:
                async with websockets.connect(self._url) as ws:
                    log.info("WS connected", machine_id=self._machine_id, url=self._url)
                    self.connected.emit()
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                            self.eventReceived.emit(msg)
                        except json.JSONDecodeError:
                            log.warning("WS: bad JSON", data=raw[:200])
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.debug(
                    "WS disconnected, reconnecting",
                    machine_id=self._machine_id,
                    error=str(exc),
                )
                self.disconnected.emit()
                if self._running:
                    await asyncio.sleep(self.RECONNECT_DELAY_S)

    def stop(self) -> None:
        """Ask the loop to exit and wait for the thread to finish."""
        self._running = False
        self.quit()
        self.wait(5000)  # 5 s timeout
