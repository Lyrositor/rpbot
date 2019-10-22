from typing import Any, Dict, List

from yaml import YAMLObject

from rpbot.data.connection import Connection
from rpbot.data.role import Role
from rpbot.data.room import Room


class Roleplay(YAMLObject):
    yaml_tag = u'!roleplay'

    def __init__(
            self,
            id: str,
            plugins: Dict[str, Dict[str, Any]],
            commands: List[str],
            roles: Dict[str, Role],
            rooms: Dict[str, Room],
            connections: List[Connection]
    ):
        self.id = id
        self.plugins = plugins
        self.commands = commands
        self.roles = roles
        self.rooms = rooms
        self.connections = connections
