from typing import Any, Dict, List, Optional

from rpbot.data.base import YAMLObjectWithDefaults
from rpbot.data.connection import Connection
from rpbot.data.role import Role
from rpbot.data.room import Room


class Roleplay(YAMLObjectWithDefaults):
    def __init__(
            self,
            id: str,
            starting_room: str,
            plugins: Dict[str, Dict[str, Any]],
            commands: List[str],
            roles: Dict[str, Role],
            description: Optional[str] = None,
            rooms: Optional[Dict[str, Room]] = None,
            connections: Optional[List[Connection]] = None
    ):
        self.id = id
        self.description = description
        self.plugins = plugins
        self.commands = commands
        self.roles = roles
        self.starting_room = starting_room
        self.rooms = rooms if rooms is not None else {}
        self.connections = connections if connections is not None else []

    def get_connection(self, room1: str, room2: str) -> Optional[Connection]:
        for connection in self.connections:
            if connection.room1 == room1 and connection.room2 == room2 \
                    or connection.room2 == room1 and connection.room1 == room2:
                return connection
        return None
