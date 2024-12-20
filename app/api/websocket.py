from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional
import asyncio
from loguru import logger
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.processing_tasks:
            self.processing_tasks[client_id].cancel()
            del self.processing_tasks[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def send_status(self, client_id: str, message: str, data: Optional[Dict] = None):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json({
                "type": "status",
                "message": message,
                "data": data
            })

    async def send_error(self, client_id: str, message: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json({
                "type": "error",
                "message": message
            })

    def register_task(self, client_id: str, task: asyncio.Task):
        self.processing_tasks[client_id] = task

manager = ConnectionManager()