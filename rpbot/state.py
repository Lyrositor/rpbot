from collections import defaultdict
from typing import Any, Dict, List

from rpbot.plugin import Plugin


class State:
    _instance = None

    def __init__(self):
        self.admins = []
        self.configs = {}
        self.plugins = defaultdict(lambda: [])

    @classmethod
    def set_admins(cls, admins: List[int]):
        if not cls._instance:
            cls._instance = State()
        cls._instance.admins = admins

    @classmethod
    def save_config(cls, guild_id: int, config: Dict[str, Any]):
        if not cls._instance:
            cls._instance = State()
        cls._instance.configs[guild_id] = config

    @classmethod
    def save_plugins(cls, guild_id: int, plugins: List[Plugin]):
        if not cls._instance:
            cls._instance = State()
        cls._instance.plugins[guild_id] = plugins

    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        if not cls._instance:
            cls._instance = State()
        return user_id in cls._instance.admins

    @classmethod
    def get_config(cls, guild_id: int) -> Dict[str, Any]:
        if not cls._instance:
            cls._instance = State()
        return cls._instance.configs[guild_id] \
            if guild_id in cls._instance.configs else None

    @classmethod
    def get_plugins(cls, guild_id: int) -> List[Plugin]:
        if not cls._instance:
            cls._instance = State()
        return cls._instance.plugins[guild_id]
