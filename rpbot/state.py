from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from discord import Member, Role

if TYPE_CHECKING:
    from rpbot.plugin import Plugin


class State:
    _instance: Optional['State'] = None

    def __init__(self):
        self.configs: Dict[int, Any] = {}
        self.plugins: Dict[int, List['Plugin']] = defaultdict(lambda: [])
        self.roles: Dict[int, Tuple[Role, Role, Role]] = {}
        self.vars = defaultdict(lambda: defaultdict(lambda: None))

    @classmethod
    def save_config(cls, guild_id: int, config: Dict[str, Any]):
        cls._setup()
        cls._instance.configs[guild_id] = config

    @classmethod
    def save_plugins(cls, guild_id: int, plugins: List['Plugin']):
        cls._setup()
        cls._instance.plugins[guild_id] = plugins

    @classmethod
    def save_roles(cls, guild_id: int, gm: Role, player: Role, observer: Role):
        cls._setup()
        cls._instance.roles[guild_id] = (gm, player, observer)

    @classmethod
    def set_var(cls, guild_id: int, var_name: str, var_value: Any):
        cls._setup()
        cls._instance.vars[guild_id][var_name] = var_value

    @classmethod
    def get_admin_role(cls, guild_id: int) -> Optional[Role]:
        return cls._get_role(guild_id, 0)

    @classmethod
    def get_player_role(cls, guild_id: int) -> Optional[Role]:
        return cls._get_role(guild_id, 1)

    @classmethod
    def get_observer_role(cls, guild_id: int) -> Optional[Role]:
        return cls._get_role(guild_id, 2)

    @classmethod
    def is_admin(cls, member: Member) -> bool:
        return cls._check_role(member, 0) or member.guild.owner.id == member.id

    @classmethod
    def is_player(cls, member: Member) -> bool:
        return cls._check_role(member, 1)

    @classmethod
    def is_observer(cls, member: Member) -> bool:
        return cls._check_role(member, 2)

    @classmethod
    def get_config(cls, guild_id: int) -> Dict[str, Any]:
        cls._setup()
        return cls._instance.configs[guild_id] \
            if guild_id in cls._instance.configs else None

    @classmethod
    def get_plugins(cls, guild_id: int) -> List['Plugin']:
        cls._setup()
        return cls._instance.plugins[guild_id]

    @classmethod
    def get_var(cls, guild_id: int, var_name: str) -> Any:
        cls._setup()
        return cls._instance.vars[guild_id][var_name]

    @classmethod
    def _setup(cls):
        if not cls._instance:
            cls._instance = State()

    @classmethod
    def _check_role(cls, member: Member, role_idx: int):
        cls._setup()
        if member.guild.id not in cls._instance.roles:
            return False
        role = cls._instance.roles[member.guild.id][role_idx]
        return any(r.id == role.id for r in member.roles)

    @classmethod
    def _get_role(cls, guild_id: int, role_idx: int):
        cls._setup()
        return cls._instance.roles[guild_id][role_idx] \
            if guild_id in cls._instance.roles else None
