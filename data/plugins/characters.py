import random
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, List

import requests
from discord import Message, Member

from rpbot.base_plugin import BasePlugin
from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommandParam, delete_message, \
    CommandException
from rpbot.state import State
from rpbot.utils import hash_password

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot

CHARACTERS_CREATE_CMD = 'charcreate'
CHARACTERS_DELETE_CMD = 'chardelete'
CHARACTERS_EDIT_CMD = 'charedit'
CHARACTERS_PASSWORD_CMD = 'charpassword'
CHARACTERS_SELECT_CMD = 'charselect'
ACTION_POINTS_CMD = 'ap'
DROP_CMD = 'drop'
INVENTORY_CMD = 'inventory'
PICKUP_CMD = 'pickup'
PRISM_CMD = 'prism'
PRISM_ADD_CMD = 'prismadd'
PRISM_RM_CMD = 'prismremove'
REFRESH_CMD = 'refresh'

NAMES_REGEX = re.compile(r'[a-z0-9 .]+')
PASSWORD_REGEX = re.compile(r'[a-zA-Z0-9]+')

STANDARD_PRISMS = {
    'Force': {
        'type': 'ability',
        'description': 'Force represents your character\'s ability to '
                       'physically affect others.'
    },
    'Presence': {
        'type': 'ability',
        'description': 'Presence represents your character\'s ability to '
                       'mentally affect others.'
    },
    'Guts': {
        'type': 'ability',
        'description': 'Guts represents your character\'s ability to '
                       'physically resist others.'
    },
    'Wits': {
        'type': 'ability',
        'description': 'Wits represents your character\'s ability to '
                       'mentally resist others.'
    },
    'Sensation': {
        'type': 'ability',
        'description': 'Sensation represents your character\'s ability to '
                       'physically examine the world.'
    },
    'Reflection': {
        'type': 'ability',
        'description': 'Reflection represents your character\'s ability to '
                       'mentally examine the world.'
    },
    'Basic': {
        'type': 'output',
        'description': 'A basic, catch-all output prism for all standard '
                       'actions any human should be capable of.',
        'tier': 0
    }
}


class CharactersPlugin(Plugin):
    def __init__(
            self, bot: 'RoleplayBot', roleplay: Roleplay, prisms: Dict[str, Any]
    ):
        super().__init__(bot, roleplay)
        self.prisms = {}
        for name, data in {**STANDARD_PRISMS, **prisms}.items():
            t = data['type']
            d = data.get('description')
            if t == 'adder':
                prism = AdderPrism(name, d, data['dice'])
            elif t == 'ability':
                prism = AbilityPrism(name, d)
            elif t == 'bonus':
                prism = BonusPrism(name, d, data['modifier'])
            elif t == 'merger':
                prism = MergerPrism(name, d, data['ability'])
            elif t == 'multiplier':
                prism = MultiplierPrism(name, d, data['modifier'])
            elif t == 'output':
                prism = OutputPrism(name, d, data['tier'])
            else:
                raise ValueError(f'Unknown prism type "{t}"')
            self.prisms[name] = prism

        self.register_command(
            name=CHARACTERS_CREATE_CMD,
            handler=self.character_create,
            help_msg='Creates a new character with the provided name.',
            requires_player=True,
            params=[PluginCommandParam('name')]
        )
        self.register_command(
            name=CHARACTERS_DELETE_CMD,
            handler=self.character_delete,
            help_msg='Deletes a character by name.',
            requires_player=True,
            params=[PluginCommandParam('name')]
        )
        self.register_command(
            name=CHARACTERS_EDIT_CMD,
            handler=self.character_edit,
            help_msg=(
                'Edits an attribute of the active character. Available '
                'attributes: `age`, `status`, `avatar`, `force`, `presence`, `guts`, '
                '`wits`, `sensation`, `reflection`.'
            ),
            requires_player=True,
            params=[
                PluginCommandParam('attribute'), PluginCommandParam('value')
            ]
        )
        self.register_command(
            name=CHARACTERS_PASSWORD_CMD,
            handler=self.character_password,
            help_msg='Sets your password for managing your character sheets.',
            requires_player=True,
            params=[PluginCommandParam('value')]
        )
        self.register_command(
            name=CHARACTERS_SELECT_CMD,
            handler=self.character_select,
            help_msg=(
                'Selects a character by name to be your active character. If '
                'no name is specified, lists available characters.'
            ),
            requires_player=True,
            params=[PluginCommandParam('name', True)]
        )
        self.register_command(
            name=ACTION_POINTS_CMD,
            handler=self.action_points,
            help_msg=(
                'Allows you to view and manipulate your action points. If a '
                'positive or negative value is provided, it will adjust your '
                'total points by that value; if no value is passed, it will '
                'display your currently available action points.'
            ),
            requires_player=True,
            params=[PluginCommandParam('points', True, 0, int)]
        )
        self.register_command(
            name=DROP_CMD,
            handler=self.drop,
            help_msg='Drops an item your character owns.',
            requires_player=True,
            requires_room=True,
            params=[PluginCommandParam('item')]
        )
        self.register_command(
            name=INVENTORY_CMD,
            handler=self.inventory,
            help_msg='Lists the contents of your character\'s inventory.',
            requires_player=True,
        )
        self.register_command(
            name=PICKUP_CMD,
            handler=self.pickup,
            help_msg=(
                'Adds an item to your inventory. You can give it a name of your'
                ' choosing.'
            ),
            requires_player=True,
            params=[PluginCommandParam('item')]
        )
        self.register_command(
            name=PRISM_CMD,
            handler=self.prism,
            help_msg=(
                'Rolls the specified list of prisms, separated by spaces. The '
                'prisms\' effects are applied in order. If no prisms are '
                'specified, lists all available prisms.'
            ),
            requires_player=True,
            params=[PluginCommandParam('prisms', collect=True)]
        )
        self.register_command(
            name=PRISM_ADD_CMD,
            handler=self.prism_add,
            help_msg=(
                'Adds a prism by name to a character. If there are multiple '
                'characters by that name, mention the owner of the character.'
            ),
            requires_admin=True,
            params=[
                PluginCommandParam('prism'),
                PluginCommandParam('character'),
                PluginCommandParam('user', True)
            ]
        )
        self.register_command(
            name=PRISM_RM_CMD,
            handler=self.prism_rm,
            help_msg=(
                'Removes a prism by name from a character. If there are '
                'multiple characters by that name, mention the owner of the '
                'character.'
            ),
            requires_admin=True,
            params=[
                PluginCommandParam('prism'),
                PluginCommandParam('character'),
                PluginCommandParam('user', True)
            ]
        )
        self.register_command(
            name=REFRESH_CMD,
            handler=self.refresh,
            help_msg=(
                'Refreshes every character\'s available action points up to the'
                ' specified number.'
            ),
            requires_admin=True,
            params=[PluginCommandParam('points', converter=int)]
        )

        if roleplay:
            for command in self.commands.values():
                command.enabled = command.name in roleplay.commands

    @delete_message
    async def character_create(self, message: Message, name: str) -> None:
        characters = await self._get_player_characters(message)

        name_id = self._get_character_id(name)
        if not NAMES_REGEX.match(name_id):
            raise CommandException(
                f'Invalid character name "{name}": only letters, numbers, '
                f'spaces and periods are allowed.'
            )

        if name_id in characters['characters']:
            raise CommandException(f'Character "{name}" already exists.')

        characters['characters'][name_id] = {
            'name': name.strip(),
            'age': None,
            'appearance': None,
            'avatar': None,
            'actions': 0,
            'status': None,
            'abilities': {
                'force': 0,
                'presence': 0,
                'guts': 0,
                'wits': 0,
                'sensation': 0,
                'reflection': 0
            },
            'inventory': [],
            'prisms': [
                'Basic',
                'Force',
                'Presence',
                'Guts',
                'Wits',
                'Sensation',
                'Reflection'
            ]
        }
        characters['active'] = name_id
        await self._save_config(message)
        await message.channel.send(f'Character "{name}" has been created.')

    @delete_message
    async def character_delete(self, message: Message, name: str) -> None:
        characters = await self._get_player_characters(message)
        name_id = self._get_character_id(name)
        if name_id not in characters['characters']:
            raise CommandException(f'Character "{name}" does not exist.')

        del characters['characters'][name_id]
        if characters['active'] == name_id:
            characters['active'] = None
        await self._save_config(message)
        await message.channel.send(f'Character "{name}" has been deleted.')

    @delete_message
    async def character_edit(
            self, message: Message, attribute: str, value: str
    ):
        character = await self._get_active_character(message)
        attr = attribute.lower()
        if attr == 'age':
            try:
                age = int(value.strip())
            except ValueError:
                age = -1
            if age < 0:
                raise CommandException(
                    f'Invalid age "{value}", must be a positive integer.'
                )
            character['age'] = age
        elif attr == 'status':
            val = value.strip()
            if len(val) > 140:
                raise CommandException(
                    f'Status `{val}` is too long, 140 characters maximum.'
                )
            character['status'] = val
        elif attr == 'appearance':
            character['appearance'] = value.strip()
        elif attr == 'avatar':
            # Check if the image exists
            response = requests.get(value)
            if response.status_code >= 400:
                raise CommandException(
                    f'Failed to fetch image from URL `{value}`'
                )
            character['avatar'] = value.strip()
        elif attr in (
                'force', 'presence', 'guts', 'wits', 'sensation', 'reflection'
        ):
            try:
                val = int(value.strip())
            except ValueError:
                val = -1
            if val < 0:
                raise CommandException(
                    f'Invalid ability "{value}", must be a positive integer.'
                )
            character['abilities'][attr] = val
        else:
            raise CommandException(f'Invalid attribute name "{attribute}"')
        await self._save_config(message)
        await message.channel.send(f'Character edited.')

    @delete_message
    async def character_password(self, message: Message, value: str) -> None:
        password = value.strip()
        if not PASSWORD_REGEX.match(password):
            raise CommandException(
                'Invalid password: can only contain letters and numbers.'
            )

        characters = await self._get_player_characters(message)
        characters['password'] = list(hash_password(password))
        await self._save_config(message)
        await message.channel.send('Password updated.')

    @delete_message
    async def character_select(
            self, message: Message, name: Optional[str] = None
    ) -> None:
        characters = await self._get_player_characters(message)

        if name is None:
            reply = 'Available characters:'
            if characters['characters']:
                for name_id, character in characters['characters'].items():
                    name = character['name']
                    is_active = characters['active'] == name_id
                    fmt = "**" if is_active else ""
                    reply += f'\n - {fmt}{name}{fmt}'
            else:
                reply += ' *None*'
            await message.channel.send(reply)
        else:
            name_id = self._get_character_id(name)
            if name_id not in characters['characters']:
                raise CommandException(f'Unknown character "{name}"')
            characters['active'] = name_id
            await self._save_config(message)
            character_name = (await self._get_active_character(message))['name']
            await message.channel.send(
                f'"{character_name}" is now the active character.'
            )

    @delete_message
    async def action_points(self, message: Message, points: int) -> None:
        character = await self._get_active_character(message)
        if points:
            character['actions'] -= points
            await self._save_config(message)
            await message.channel.send(
                f'{character["name"]} now has {character["actions"]} action '
                f'points.'
            )
        else:
            await message.channel.send(
                f'{character["name"]} has {character["actions"]} action points.'
            )

    @delete_message
    async def drop(self, message: Message, item: str) -> None:
        character = await self._get_active_character(message)
        item_clean = item.strip()
        if item_clean not in character['inventory']:
            raise CommandException(
                f'{character["name"]} does not own "{item_clean}".'
            )
        character['inventory'].remove(item_clean)
        await self._save_config(message)
        await message.channel.send(f'Dropped "{item_clean}".')
        await self.bot.get_chronicle(message.guild).log_from_channel(
            message.channel,
            f'**{character["name"]}** dropped **{item_clean}**',
        )

    @delete_message
    async def pickup(self, message: Message, item: str) -> None:
        character = await self._get_active_character(message)
        item_clean = item.strip()
        character['inventory'].append(item_clean)
        await self._save_config(message)
        await message.channel.send(f'Picked up "{item_clean}".')
        await self.bot.get_chronicle(message.guild).log_from_channel(
            message.channel,
            f'**{character["name"]}** picked up **{item_clean}**',
        )

    @delete_message
    async def inventory(self, message: Message) -> None:
        character = await self._get_active_character(message)
        items = 'Inventory:'
        if character['inventory']:
            for item in character['inventory']:
                items += f'\n - {item}'
        else:
            items += ' *Empty*'
        await message.channel.send(items)

    @delete_message
    async def prism(self, message: Message, prisms: List[str]) -> None:
        character = await self._get_active_character(message)

        prism_summaries = []
        roll = Roll()
        for prism_query in prisms:
            prism = self._find_prism(character, prism_query.strip())
            prism.apply(character, roll)
            prism_summaries.append(f'**{prism.name}** [{prism.summary}]')
        result = roll.resolve()

        msg = (
            f'{message.author.mention} rolled: **{result.total}** '
            f'({result.dice_total} + {result.modifier})'
        )
        if result.rerolls:
            msg += f' (**{result.rerolls}** rerolls left)'
        msg += '\n*' + ' > '.join(prism_summaries) + '*'
        msg += '\n' + ' '.join(BasePlugin.NUMBERS_EMOJI[r] for r in result.dice)

        await message.channel.send(msg)
        await self.bot.get_chronicle(message.guild).log_roll(
            message.author, message.channel, result.total
        )

    # noinspection PyUnusedLocal
    @delete_message
    async def prism_add(
            self, message: Message, prism: str, character: str, user: str
    ) -> None:
        character = await self._get_character_by_name_and_mention(
            message, character, message.mentions[0]
        )
        if not character:
            return
        prism_clean = prism.strip()
        if prism_clean in character['prisms']:
            raise CommandException(
                f'{character["name"]} already owns "{prism_clean}".'
            )
        character['prisms'].append(prism_clean)
        await self._save_config(message)
        await message.channel.send(
            f'Gave "{prism_clean}" to {character["name"]}.'
        )

    # noinspection PyUnusedLocal
    @delete_message
    async def prism_rm(
            self, message: Message, prism: str, character: str, user: str
    ) -> None:
        character = await self._get_character_by_name_and_mention(
            message, character, message.mentions[0]
        )
        if not character:
            return
        prism_clean = prism.strip()
        if prism_clean not in character['prisms']:
            raise CommandException(
                f'{character["name"]} does not own "{prism_clean}".'
            )
        character['prisms'].remove(prism_clean)
        await self._save_config(message)
        await message.channel.send(
            f'Removed "{prism_clean}" from {character["name"]}.'
        )

    @delete_message
    async def refresh(self, message: Message, points: int):
        characters_by_player = await self._get_characters_by_player(message)
        if characters_by_player is None:
            return None

        for user_id, entry in characters_by_player.items():
            for character in entry['characters'].values():
                character['actions'] = points

        await self._save_config(message)
        await message.channel.send(f'Actions points refreshed to {points}.')

    async def _save_config(self, message: Message) -> None:
        await self.bot.save_guild_config(
            message.guild, State.get_config(message.guild.id)
        )

    async def _get_active_character(self, message: Message) -> Dict[str, Any]:
        characters = await self._get_player_characters(message)
        active = characters['characters'].get(characters['active'])
        if not active:
            raise CommandException(
                f'No active character selected. Use {CHARACTERS_SELECT_CMD} to '
                f'pick one.'
            )
        return active

    @staticmethod
    async def _get_player_characters(message: Message) -> Dict[str, Any]:
        config = State.get_config(message.guild.id)
        if not config or not config.get('rp'):
            raise CommandException(
                'No active roleplay, characters not available.'
            )
        if 'characters' not in config:
            config['characters'] = {}
        user_id = str(message.author.id)
        if user_id not in config['characters']:
            config['characters'][user_id] = {
                'password': None,
                'active': None,
                'characters': {}
            }
        return config['characters'][user_id]

    async def _get_character_by_name_and_mention(
            self, message: Message, character_name: str, mention: Member
    ) -> Optional[Dict[str, Any]]:
        characters_by_player = await self._get_characters_by_player(message)

        user_id = str(mention.id)
        if user_id not in characters_by_player:
            raise CommandException('No characters set up for user.')

        characters = characters_by_player[user_id]['characters']
        query = self._get_character_id(character_name)
        for name, value in characters.items():
            if name.startswith(query):
                return value

        raise CommandException(f'Failed to locate character.')

    @staticmethod
    async def _get_characters_by_player(
            message: Message
    ) -> Dict[str, Dict[str, Any]]:
        config = State.get_config(message.guild.id)
        if not config or not config.get('rp'):
            raise CommandException(
                'No active roleplay, characters not available.'
            )

        if 'characters' not in config:
            raise CommandException('Characters are not set up.')

        return config['characters']

    @staticmethod
    def _get_character_id(name: str):
        return name.lower().strip()

    def _find_prism(self, character: Dict[str, Any], query: str) -> 'Prism':
        for prism in character['prisms']:
            if prism.lower().startswith(query.lower()):
                prism_name = prism
                break
        else:
            raise CommandException(f'Character does not own prism "{query}".')
        prism = self.prisms.get(prism_name)
        if not prism:
            raise CommandException(f'Unknown prism "{prism_name}".')
        return prism


class RollResult:
    dice: List[int]
    modifier: int
    rerolls: int

    def __init__(self, modifier: int, rerolls: int):
        self.dice = []
        self.modifier = modifier
        self.rerolls = rerolls

    @property
    def dice_total(self) -> int:
        return sum(self.dice)

    @property
    def total(self) -> int:
        return self.dice_total + self.modifier

    def add_roll(self) -> None:
        self.dice.append(random.randint(1, 6))

    def __str__(self):
        return (
            'Roll: '
            ' + '.join(f'[{d}]' for d in self.dice) if self.dice else '[0]'
            f' + {self.modifier}' if self.modifier else ''
            f' = {sum(self.dice)}'
            f' ({self.rerolls} rerolls left)' if self.rerolls else ''
        )


class Roll:
    num_dice: int
    modifier: int
    rerolls: int

    def __init__(self, num_dice: int = 0, modifier: int = 0, rerolls: int = 0):
        self.num_dice = num_dice
        self.modifier = modifier
        self.rerolls = rerolls

    def resolve(self) -> RollResult:
        result = RollResult(modifier=self.modifier, rerolls=self.rerolls)
        for _ in range(self.num_dice):
            result.add_roll()
        return result


class Prism(ABC):
    name: str
    description: str

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @property
    def summary(self):
        return '???'

    @abstractmethod
    def apply(self, character: Dict[str, Any], roll: Roll) -> Roll:
        raise NotImplementedError


class AdderPrism(Prism):
    num_dice: int

    def __init__(self, name: str, description: str, num_dice: int):
        super().__init__(name, description)
        self.num_dice = num_dice

    @property
    def summary(self):
        return f'Adder, {self.num_dice}'

    def apply(self, character: Dict[str, Any], roll: Roll) -> None:
        roll.num_dice += self.num_dice


class AbilityPrism(Prism):
    @property
    def summary(self):
        return f'Ability'

    def apply(self, character: Dict[str, Any], roll: Roll) -> None:
        roll.num_dice += character['abilities'][self.name.lower()]


class BonusPrism(Prism):
    modifier: int

    def __init__(self, name: str, description: str, modifier: int):
        super().__init__(name, description)
        self.modifier = modifier

    @property
    def summary(self):
        return f'Bonus, {"+" if self.modifier > 0 else ""}{self.modifier}'

    def apply(self, character: Dict[str, Any], roll: Roll) -> None:
        roll.modifier += self.modifier


class MergerPrism(Prism):
    ability: str

    def __init__(self, name: str, description: str, ability: str):
        super().__init__(name, description)
        self.ability = ability

    @property
    def summary(self):
        return f'Merger, {self.ability}'

    def apply(self, character: Dict[str, Any], roll: Roll) -> None:
        roll.num_dice += character['abilities'][self.ability.lower()]


class MultiplierPrism(Prism):
    multiplier: int

    def __init__(self, name: str, description: str, multiplier: int):
        super().__init__(name, description)
        self.multiplier = multiplier

    @property
    def summary(self):
        return f'Multiplier, x{self.multiplier}'

    def apply(self, character: Dict[str, Any], roll: Roll) -> None:
        roll.num_dice *= self.multiplier


class OutputPrism(Prism):
    tier: int

    def __init__(self, name: str, description: str, tier: int):
        super().__init__(name, description)
        self.tier = tier

    @property
    def summary(self):
        return f'Output, Tier {self.tier}'

    def apply(self, character: Dict[str, Any], roll: Roll) -> None:
        roll.rerolls += self.tier


PLUGIN = CharactersPlugin
