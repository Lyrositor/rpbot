from typing import Any, Dict, List, Optional

from yaml import YAMLObject

from rpbot.data.connection import Connection
from rpbot.data.role import Role
from rpbot.data.room import Room


class Roleplay(YAMLObject):
    yaml_tag = u'!roleplay'

    def __init__(
            self,
            id: str,
            description: str,
            plugins: Dict[str, Dict[str, Any]],
            commands: List[str],
            roles: Dict[str, Role],
            starting_room: str,
            rooms: Dict[str, Room],
            connections: List[Connection]
    ):
        self.id = id
        self.description = description
        self.plugins = plugins
        self.commands = commands
        self.roles = roles
        self.starting_room = starting_room
        self.rooms = rooms
        self.connections = connections

    def get_connection(self, room1: str, room2: str) -> Optional[Connection]:
        for connection in self.connections:
            if connection.room1 == room1 and connection.room2 == room2 \
                    or connection.room2 == room1 and connection.room1 == room2:
                return connection
        return None
