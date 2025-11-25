from typing import Dict, Set
from fastapi import WebSocket
from app.core.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections per room.
    """

    def __init__(self) -> None:
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, room_id: int, websocket: WebSocket) -> None:
        """
        Accept the connection and register it under the given room.
        """
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        self.active_connections[room_id].add(websocket)
        logger.info("WebSocket accepted for room %s (connections=%s)", room_id, len(self.active_connections.get(room_id, [])))

    def disconnect(self, room_id: int, websocket: WebSocket) -> None:
        """
        Remove a WebSocket from the room.
        """
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        logger.info("WebSocket disconnected for room %s (remaining=%s)", room_id, len(self.active_connections.get(room_id, [])) if room_id in self.active_connections else 0)

    async def broadcast(self, room_id: int, message: dict) -> None:
        """
        Broadcast a JSON-serializable message to all connections in a room.
        """
        connections = self.active_connections.get(room_id)
        if not connections:
            logger.debug("No connections to broadcast to for room %s", room_id)
            return

        logger.debug("Broadcasting message to %s connections in room %s", len(connections), room_id)

        dead = []
        for ws in list(connections):
            try:
                await ws.send_json(message)
            except Exception:
                logger.exception("Error sending message to websocket in room %s", room_id)
                dead.append(ws)

        for ws in dead:
            connections.discard(ws)
