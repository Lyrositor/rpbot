import logging
from abc import ABC, abstractmethod
from functools import wraps
from typing import Callable, Optional, List, Any, Dict, TYPE_CHECKING, Tuple

from discord import Message, Guild
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

    def register_command(
            self,
            name: str,
            handler: Callable,
            help_msg: Optional[str] = None,
            requires_player: bool = False,
            requires_admin: bool = False,
            requires_room: bool = False,
            params: Optional[List['PluginCommandParam']] = None
    ):
        self.commands[name] = PluginCommand(
            name=name,
            handler=handler,
            help_msg=help_msg,
            requires_player=requires_player,
            requires_admin=requires_admin,
            requires_room=requires_room,
            params=params
        )

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
            if spec.requires_room and (
                    not self.roleplay
                    or message.channel.name not in self.roleplay.rooms
            ):
                return True
            await spec.run(message, params)
        except CommandException as e:
            await message.channel.send(str(e))
            await message.add_reaction('🚫')
        except Exception:
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

    def get_help(self, is_admin: bool) -> str:
        return '\n'.join(
            str(self.commands[c]) for c in sorted(self.commands.keys())
            if (not self.commands[c].requires_admin or is_admin)
            and self.commands[c].enabled
        )


class PluginCommand:
    PREFIX = '!'

    def __init__(
            self,
            name: str,
            handler: Callable,
            help_msg: Optional[str] = None,
            requires_player: bool = False,
            requires_admin: bool = False,
            requires_room: bool = False,
            params: Optional[List['PluginCommandParam']] = None,
            enabled: bool = False
    ):
        self.name = name
        self.handler = handler
        self.help = help_msg
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
            raise CommandException(
                f'{message.author} is not authorised to use command '
                f'{self.PREFIX}{self.name}'
            )

        if not self.enabled:
            raise CommandException(
                f'Command {self.PREFIX}{self.name} is disabled'
            )

        # Messy code to primitively try to handle quoted strings
        # The last argument is always taken entirely as-is, quotes included
        param_values = []
        idx = 0
        if params is not None:
            for i, param in enumerate(self.params):
                is_last = i == (len(self.params) - 1)
                while idx < len(params):
                    if is_last and not param.collect:
                        param_value, idx = params[idx:], len(params)
                    else:
                        param_value, idx = _get_param_value(params, idx)
                    param_values.append(param_value.strip())
                    if not param.collect:
                        break

        processed_params = []
        for i, param in enumerate(self.params):
            if i < len(param_values):
                if param.collect:
                    value = param_values[i:]
                else:
                    value = param_values[i]
            else:
                value = None
            processed_params.append(param.process(value))
        await self.handler(message, *processed_params)

    def __str__(self):
        return \
            f'**{self.PREFIX}{self.name} ' \
            + ''.join(
                f'*{p.name}* ' if p.optional else f'{p.name} '
                for p in self.params
            ) \
            + (f'**- {self.help}' if self.help else '**')


class PluginCommandParam:
    def __init__(
            self,
            name: str,
            optional: bool = False,
            default: Any = None,
            converter: Optional[Callable] = None,
            collect: bool = False
    ):
        self.name = name
        self.optional = optional
        self.default = default
        self.converter = converter
        self.collect = collect

    def process(self, value) -> Any:
        if not value:
            if self.optional:
                return self.default
            raise CommandException(
                f'Invalid value for parameter "{self.name}": "{value}"'
            )
        return self.converter(value) if self.converter else value


class CommandException(Exception):
    pass


def delete_message(func: Callable) -> Callable:
    @wraps(func)
    async def new_func(self, message: Message, *args, **kwargs):
        result = await func(self, message, *args, **kwargs)
        await message.delete()
        return result
    return new_func


def _get_param_value(string: str, idx: int) -> Tuple[str, int]:
    idx = _consume_whitespace(string, idx)
    c = string[idx]
    if c == '"':
        idx += 1
        param, idx = _consume_until(string, idx, '"')
        idx += 1
        if idx < len(string) and string[idx] != " ":
            raise CommandException(f'Invalid parameters: {string}')
    else:
        param, idx = _consume_until(string, idx, ' ')
    return param, idx


def _consume_whitespace(string: str, idx: int) -> int:
    while idx < len(string) and string[idx] == ' ':
        idx += 1
    return idx


def _consume_until(string: str, idx: int, char: str) -> Tuple[str, int]:
    bit = ''
    while idx < len(string) and string[idx] != char:
        bit += string[idx]
        idx += 1
    return bit, idx
