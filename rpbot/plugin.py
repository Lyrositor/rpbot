import logging
from abc import ABC, abstractmethod
from typing import Callable, Optional, List, Any, Dict, TYPE_CHECKING, Union

from discord import Message, Guild, CategoryChannel
from discord.abc import GuildChannel

from rpbot.data.roleplay import Roleplay
from rpbot.state import State

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot


class Plugin(ABC):

    @abstractmethod
    def __init__(self, bot: 'RoleplayBot', roleplay: Roleplay):
        self.bot = bot
        self.roleplay = roleplay
        self.commands: Dict[str, PluginCommand] = {}

    async def process_message(self, message: Message) -> bool:
        return await self.check_for_command(message)

    async def check_for_command(self, message: Message) -> bool:
        m = message.clean_content
        if not m.startswith(PluginCommand.PREFIX):
            return False
        m_split = m[1:].split(' ', 1)
        command = m_split[0]
        full_command = PluginCommand.PREFIX + command
        params = None
        if len(m_split) > 1:
            params = m_split[1]
        if command not in self.commands:
            return False

        try:
            spec = self.commands[command]
            if message.channel.name not in self.roleplay.rooms \
                    and spec.requires_room:
                return True
            await spec.run(message, params)
        except:
            logging.exception(
                f'Failed to process command {full_command} '
                f'from {message.author}'
            )
            await message.add_reaction('🚫')
        else:
            logging.info(
                f'Successfully processed command {full_command} from '
                f'{message.author}'
            )
        return True

    @classmethod
    def find_channel_by_name(
            cls, guild: Guild, name: str, category=None
    ) -> Optional[GuildChannel]:
        source = guild
        if category:
            source = cls.find_channel_by_name(guild, category)
        if not source:
            return None
        for channel in source.channels:
            if channel.name == name:
                return channel
        return None

    def get_help(self):
        return '\n'.join(
            str(self.commands[c]) for c in sorted(self.commands.keys())
            if not self.commands[c].requires_admin and self.commands[c].enabled
        )


class PluginCommand:
    PREFIX = '!'

    def __init__(
            self,
            name: str,
            handler: Callable,
            help: Optional[str] = None,
            requires_player: bool = False,
            requires_admin: bool = False,
            requires_room: bool = False,
            params: Optional[List['PluginCommandParam']] = None,
            enabled: bool = True
    ):
        self.name = name
        self.handler = handler
        self.help = help
        self.requires_player = requires_player
        self.requires_admin = requires_admin
        self.requires_room = requires_room
        self.params = params if params else []
        self.enabled = enabled

    async def run(self, message: Message, params: Optional[str]):
        is_admin = State.is_admin(message.author)
        is_player = State.is_player(message.author)

        if self.requires_admin and not is_admin\
                or self.requires_player and not (is_player or is_admin):
            raise Exception(
                f'{message.author} is not authorised to use command '
                f'{self.PREFIX}{self.name}'
            )

        if not self.enabled:
            raise Exception(f'Command {self.PREFIX}{self.name} is disabled')

        param_values = params.split(' ', len(self.params)) if params else []
        processed_params = []
        for i, param in enumerate(self.params):
            value = param_values[i] if i < len(param_values) else None
            processed_params.append(param.process(value))
        await self.handler(message, *processed_params)

    def __str__(self):
        return \
            f'**{self.PREFIX}{self.name} ' \
            + ''.join(
                f'*{p.name}* ' if not p.optional else f'{p.name} '
                for p in self.params
            ) \
            + (f'**- {self.help}' if self.help else '')


class PluginCommandParam:
    def __init__(
            self,
            name: str,
            optional: bool = False,
            default: Any = None,
            converter: Optional[Callable] = None
    ):
        self.name = name
        self.optional = optional
        self.default = default
        self.converter = converter

    def process(self, value) -> Any:
        if not value:
            if self.optional:
                return self.default
            raise ValueError(
                f'Invalid value for parameter {self.name}: "{value}"'
            )
        return self.converter(value) if self.converter else value
