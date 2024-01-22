from fastapi import WebSocket
from typing import Dict

from models import Message


class ConnectionHandler(object):

    active_sockets: Dict[int, Dict[int, WebSocket]]

    def __init__(self) -> None:
        self.active_sockets = dict()

    def register(self, chat_id: int, user_id: int, websocket: WebSocket) -> None:
        self.active_sockets.setdefault(chat_id, dict())
        self.active_sockets[chat_id][user_id] = websocket

    async def broadcast(self, chat_id: int, message: Message) -> None:
        for websocket in self.active_sockets[chat_id].values():
            await websocket.send_json(message)

    def close(self, chat_id: int, user_id: int) -> None:
        self.active_sockets.setdefault(chat_id, dict())
        self.active_sockets[chat_id].pop(user_id, None)


connection_handler = ConnectionHandler()
