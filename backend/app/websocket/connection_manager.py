import json
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

class ConnectionManager:
    """
    Manages real-time WebSocket clients and broadcasts versioned system events,
    form updates, task logs, and stale block notifications to connected frontends.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts JSON payload to all active WebSocket clients."""
        payload_str = json.dumps(message)
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(payload_str)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)
