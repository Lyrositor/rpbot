import random
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, List, Iterable, Union, \
    Tuple

import requests
from discord import Message, Member, Guild, TextChannel, Reaction, User

from rpbot.base_plugin import BasePlugin
from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommandParam, delete_message, \
    CommandException
from rpbot.state import State
from rpbot.utils import hash_password, reply

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot

CHARACTERS_CREATE_CMD = 'charcreate'
CHARACTERS_DELETE_CMD = 'chardelete'
CHARACTERS_EDIT_CMD = 'charedit'
CHARACTERS_PASSWORD_CMD = 'charpassword'
CHARACTERS_SELECT_CMD = 'charselect'
NPC_MOVE_CMD = 'npcmove'
NPC_PRISM_CMD = 'npcprism'
ACTION_POINTS_CMD = 'ap'
DROP_CMD = 'drop'
INVENTORY_CMD = 'inventory'
PICKUP_CMD = 'pickup'
PRISM_CMD = 'prism'
PRISM_ADD_CMD = 'prismadd'
PRISM_RM_CMD = 'prismremove'
PRISM_FAKE_CMD = 'prismfake'
REFRESH_CMD = 'refresh'
STATUS_CMD = 'status'

NAMES_REGEX = re.compile(r'[a-z0-9 .]+')
PASSWORD_REGEX = re.compile(r'[a-zA-Z0-9]+')
PRISM_ROLL_REGEX = re.compile(r'^(.*?)(?:\[(.*)])?$')

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
            self,
            bot: 'RoleplayBot',
            roleplay: Roleplay,
            prisms: Dict[str, Any],
            npcs: Dict[str, Any]
    ):
        super().__init__(bot, roleplay)
        self.prisms = {}
        self.npcs = {}
        self.rerolls = {}
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
            elif t == 'faker':
                prism = FakerPrism(name, d)
            elif t == 'weighter':
                prism = WeighterPrism(name, d, data['weights'])
            elif t == 'special':
                prism = SpecialPrism(name, d, data.get('param_type'))
            else:
                raise ValueError(f'Unknown prism type "{t}"')
            self.prisms[name] = prism
        for name, data in npcs.items():
            for prism in data['prisms']:
                if prism not in self.prisms:
                    raise ValueError(f'Unknown NPC prism "{prism}"')
            self.npcs[self._get_character_id(name)] = {'name': name, **data}

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
                'attributes: `age`, `status`, `avatar`, `force`, `presence`, '
                '`guts`, `wits`, `sensation`, `reflection`.'
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
            name=NPC_MOVE_CMD,
            handler=self.npc_move,
            help_msg='Moves an NPC to the specified room.',
            requires_admin=True,
            params=[PluginCommandParam('name'), PluginCommandParam('room')]
        )
        self.register_command(
            name=NPC_PRISM_CMD,
            handler=self.npc_prism,
            help_msg=(
                'Rolls prisms for an NPC. Specify no prisms to list all of the '
                'NPC\'s prisms instead.'
            ),
            requires_admin=True,
            params=[
                PluginCommandParam('name'),
                PluginCommandParam('prisms', optional=True, collect=True)
            ]
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
            params=[PluginCommandParam('prisms', optional=True, collect=True)]
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
            name=PRISM_FAKE_CMD,
            handler=self.prism_fake,
            help_msg='Fakes a prism roll.',
            hidden=True,
            params=[
                PluginCommandParam('result', converter=int),
                PluginCommandParam('prisms', optional=True, collect=True)
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
        self.register_command(
            name=STATUS_CMD,
            handler=self.status,
            requires_player=True,
            requires_room=True,
            help_msg=(
                'Displays the current status of all characters in the vicinity.'
            ),
        )

        if roleplay:
            for command in self.commands.values():
                command.enabled = command.name in roleplay.commands

    async def process_react(
            self, reaction: Reaction, user: Union[Member, User]
    ) -> bool:
        message_id = reaction.message.id
        if reaction.emoji == '🔄' and message_id in self.rerolls:
            reroll_info = self.rerolls[message_id]
            if reroll_info['user'] == user.id:
                await reroll_info['callback']()
                await reaction.clear()
                del self.rerolls[message_id]
                return True
        return False

    @delete_message
    async def character_create(self, message: Message, name: str) -> None:
        characters = await self._get_player_characters(message.author)

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
        await self._save_config(message.guild)
        await message.channel.send(f'Character "{name}" has been created.')

    @delete_message
    async def character_delete(self, message: Message, name: str) -> None:
        characters = await self._get_player_characters(message.author)
        name_id = self._get_character_id(name)
        if name_id not in characters['characters']:
            raise CommandException(f'Character "{name}" does not exist.')

        del characters['characters'][name_id]
        if characters['active'] == name_id:
            characters['active'] = None
        await self._save_config(message.guild)
        await message.channel.send(f'Character "{name}" has been deleted.')

    @delete_message
    async def character_edit(
            self, message: Message, attribute: str, value: str
    ):
        character = await self._get_active_character(message.author)
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
        await self._save_config(message.guild)
        await message.channel.send(f'Character edited.')

    @delete_message
    async def character_password(self, message: Message, value: str) -> None:
        password = value.strip()
        if not PASSWORD_REGEX.match(password):
            raise CommandException(
                'Invalid password: can only contain letters and numbers.'
            )

        characters = await self._get_player_characters(message.author)
        characters['password'] = list(hash_password(password))
        await self._save_config(message.guild)
        await message.channel.send('Password updated.')

    @delete_message
    async def character_select(
            self, message: Message, name: Optional[str] = None
    ) -> None:
        characters = await self._get_player_characters(message.author)

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
            await self._save_config(message.guild)
            character_name = (await self._get_active_character(
                message.author
            ))['name']
            await message.channel.send(
                f'"{character_name}" is now the active character.'
            )

    @delete_message
    async def npc_move(self, message: Message, npc_name: str, new_room: str):
        new_channel = self.find_channel_by_name(
            message.guild, new_room, self.roleplay.rooms[new_room].section
        )
        if not new_channel:
            raise CommandException(f'Invalid room "{new_room}"')
        assert isinstance(new_channel, TextChannel)

        npc = await self._get_npc_by_name(npc_name)
        in_room = message.channel.name in self.roleplay.rooms
        await self._move_npc_to_room(message.guild, npc['name'], new_room)
        if in_room:
            await message.channel.send(f'**{npc["name"]}** moves to {new_room}')
            await new_channel.send(
                f'**{npc["name"]}** moves in from {message.channel.name}'
            )
        else:
            await new_channel.send(f'**{npc["name"]}** appears')
        await self.bot.get_chronicle(message.guild).log_movement(
            npc['name'], new_room, message.channel if in_room else None
        )

    @delete_message
    async def npc_prism(
            self, message: Message, npc_name: str, prisms: Optional[List[str]]
    ) -> None:
        npc = await self._get_npc_by_name(npc_name)
        await self._roll_prisms(message.channel, message.author, npc, prisms)

    @delete_message
    async def action_points(self, message: Message, points: int) -> None:
        character = await self._get_active_character(message.author)
        if points:
            character['actions'] -= points
            await self._save_config(message.guild)
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
        character = await self._get_active_character(message.author)
        item_clean = item.strip()
        if item_clean not in character['inventory']:
            raise CommandException(
                f'{character["name"]} does not own "{item_clean}".'
            )
        character['inventory'].remove(item_clean)
        await self._save_config(message.guild)
        await message.channel.send(f'Dropped "{item_clean}".')
        await self.bot.get_chronicle(message.guild).log_from_channel(
            message.channel,
            f'**{character["name"]}** dropped **{item_clean}**',
        )

    @delete_message
    async def pickup(self, message: Message, item: str) -> None:
        character = await self._get_active_character(message.author)
        item_clean = item.strip()
        character['inventory'].append(item_clean)
        await self._save_config(message.guild)
        await message.channel.send(f'Picked up "{item_clean}".')
        await self.bot.get_chronicle(message.guild).log_from_channel(
            message.channel,
            f'**{character["name"]}** picked up **{item_clean}**',
        )

    @delete_message
    async def inventory(self, message: Message) -> None:
        character = await self._get_active_character(message.author)
        items = 'Inventory:'
        if character['inventory']:
            for item in character['inventory']:
                items += f'\n - {item}'
        else:
            items += ' *Empty*'
        await message.channel.send(items)

    @delete_message
    async def prism(self, message: Message, prisms: Optional[List[str]]) -> None:
        character = await self._get_active_character(message.author)
        await self._roll_prisms(message.channel, message.author, character, prisms)

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
        await self._save_config(message.guild)
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
        await self._save_config(message.guild)
        await message.channel.send(
            f'Removed "{prism_clean}" from {character["name"]}.'
        )

    @delete_message
    async def prism_fake(
            self, message: Message, result: int, prisms: Optional[List[str]]
    ) -> None:
        character = await self._get_active_character(message.author)
        has_faker = False
        if prisms:
            for prism_query in prisms:
                prism = self._find_prism(character, prism_query.strip())
                has_faker |= isinstance(prism, FakerPrism)
        if not has_faker:
            await message.channel.send(f'No valid prism for roll.')
            return
        await self._roll_prisms(
            message.channel, message.author, character, prisms, result
        )

    @delete_message
    async def refresh(self, message: Message, points: int) -> None:
        characters_by_player = await self._get_characters_by_player(message)
        if characters_by_player is None:
            return None

        for user_id, entry in characters_by_player.items():
            for character in entry['characters'].values():
                character['actions'] = points

        await self._save_config(message.guild)
        await message.channel.send(f'Actions points refreshed to {points}.')

    @delete_message
    async def status(self, message: Message) -> None:
        statuses = []
        for member in message.channel.members:
            if State.is_player(member):
                try:
                    character = await self._get_active_character(member)
                except CommandException:
                    continue
                if character['status']:
                    status = f'**{character["name"]}:** {character["status"]}'
                else:
                    status = f'**{character["name"]}**'
                statuses.append(status)
        for npc in self._get_npcs_in_room(
                message.guild, message.channel.name
        ):
            statuses.append(f'**{npc["name"]}:** {npc["description"]}')

        if statuses:
            text = 'The following people are here:'
            for status in sorted(statuses):
                text += f'\n{status}'
            await reply(message, text)
        else:
            await reply(message, 'Nobody is here.')

    async def _save_config(self, guild: Guild) -> None:
        await self.bot.save_guild_config(
            guild, State.get_config(guild.id)
        )

    async def _get_active_character(self, member: Member) -> Dict[str, Any]:
        characters = await self._get_player_characters(member)
        active = characters['characters'].get(characters['active'])
        if not active:
            raise CommandException(
                f'No active character selected. Use {CHARACTERS_SELECT_CMD} to '
                f'pick one.'
            )
        return active

    async def _get_player_characters(self, member: Member) -> Dict[str, Any]:
        config = self._get_config(member.guild)
        if 'characters' not in config:
            config['characters'] = {}
        user_id = str(member.id)
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

    async def _get_characters_by_player(
            self, message: Message
    ) -> Dict[str, Dict[str, Any]]:
        config = self._get_config(message.guild)
        if 'characters' not in config:
            raise CommandException('Characters are not set up.')
        return config['characters']

    @staticmethod
    def _get_character_id(name: str):
        return name.lower().strip()

    def _find_prism(self, character: Dict[str, Any], query: str) -> 'Prism':
        for prism in self._get_all_prisms(character):
            if prism.lower().startswith(query.lower()):
                prism_name = prism
                break
        else:
            raise CommandException(f'Character does not own prism "{query}".')
        prism = self.prisms.get(prism_name)
        if not prism:
            raise CommandException(f'Unknown prism "{prism_name}".')
        return prism

    @staticmethod
    def _get_all_prisms(character: Dict[str, Any]) -> List[str]:
        all_prisms = [*character['prisms']]
        for prism_name in STANDARD_PRISMS:
            if prism_name not in all_prisms:
                all_prisms.append(prism_name)
        return all_prisms

    async def _get_npc_by_name(self, npc_name: str) -> Dict[str, Any]:
        query = self._get_character_id(npc_name)
        for npc_id, value in self.npcs.items():
            if npc_id.startswith(query):
                return value
        raise CommandException(f'Failed to locate NPC.')

    def _get_npcs_in_room(
            self, guild: Guild, room: str
    ) -> List[Dict[str, Any]]:
        npcs_config = self._get_npcs_config(guild)
        return [
            self.npcs[npc_id]
            for npc_id in npcs_config['rooms'].get(room, [])
        ]

    async def _move_npc_to_room(
            self, guild: Guild, npc_name: str, new_room: str
    ) -> None:
        npcs_config = self._get_npcs_config(guild)
        npc_id = self._get_character_id(npc_name)
        for room, npcs in npcs_config['rooms'].items():
            if npc_id in npcs:
                npcs.remove(npc_id)
        if new_room not in npcs_config['rooms']:
            npcs_config['rooms'][new_room] = []
        npcs_config['rooms'][new_room].append(npc_id)
        await self._save_config(guild)

    def _get_npcs_config(self, guild: Guild) -> Dict[str, Any]:
        config = self._get_config(guild)
        if 'npcs' not in config:
            config['npcs'] = {'rooms': {}}
        return config['npcs']

    async def _roll_prisms(
            self,
            channel: TextChannel,
            author: User,
            character: Dict[str, Any],
            prisms: Optional[Iterable[str]],
            force_result: Optional[int] = None,
            rerolls_left: Optional[int] = None
    ) -> None:
        if not prisms:
            msg = f'**{character["name"]}** owns the following prisms:'
            for prism_name in self._get_all_prisms(character):
                prism = self.prisms[prism_name]
                msg += f'\n- {prism}'
            await channel.send(msg)
            return
        prism_summaries = []
        roll = Roll()
        rolled_prism_names = set()
        for prism_cmd in prisms:
            match = PRISM_ROLL_REGEX.match(prism_cmd)
            prism_query = match.group(1)
            prism_param = match.group(2)
            prism = self._find_prism(character, prism_query.strip())
            prism.apply(
                character,
                roll,
                prism_param if isinstance(prism, SpecialPrism) else None
            )
            rolled_prism_names.add(prism.name.lower().strip())
            prism_summaries.append(f'**{prism.name}** [{prism.summary}]')
        result = roll.resolve(force_result)
        if rerolls_left is not None:
            result.rerolls = rerolls_left

        msg = (
            f'{character["name"]} rolled: **{result.total}** '
            f'({result.dice_total} + {result.modifier})'
        )
        if result.rerolls:
            msg += f' (**{result.rerolls}** rerolls left)'
        msg += '\n*' + ' > '.join(prism_summaries) + '*'
        msg += '\n' + ' '.join(BasePlugin.NUMBERS_EMOJI[r] for r in result.dice)

        message = await channel.send(msg)
        if result.rerolls > 0:
            async def reroll_func():
                await self._roll_prisms(
                    channel,
                    author,
                    character,
                    prisms,
                    force_result,
                    result.rerolls - 1
                )
            self.rerolls[message.id] = {
                'user': author.id,
                'callback': reroll_func
            }
            await message.add_reaction('🔄')
            if "laika" in rolled_prism_names:
                await message.add_reaction('🐶')
        await self.bot.get_chronicle(channel.guild).log_roll(
            character["name"], channel, result.total
        )

    @staticmethod
    def _get_config(guild: Guild) -> Dict[str, Any]:
        config = State.get_config(guild.id)
        if not config or not config.get('rp'):
            raise CommandException(
                'No active roleplay, characters not available.'
            )
        return config


class RollResult:
    dice: List[int]
    modifier: int
    rerolls: int
    weights: Optional[Tuple[int, int, int, int, int, int]]

    def __init__(
            self,
            modifier: int,
            rerolls: int,
            weights: Optional[Tuple[int, int, int, int, int, int]] = None
    ):
        self.dice = []
        self.modifier = modifier
        self.rerolls = rerolls
        self.weights = weights

    @property
    def dice_total(self) -> int:
        return sum(self.dice)

    @property
    def total(self) -> int:
        return self.dice_total + self.modifier

    def add_roll(self, forced_result: Optional[int] = None) -> None:
        self.dice.append(
            forced_result if forced_result is not None else self._get_roll()
        )

    def _get_roll(self) -> int:
        if self.weights:
            return random.choices((1, 2, 3, 4, 5, 6), self.weights)[0]
        else:
            return random.randint(1, 6)

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
    weights: Optional[Tuple[int, int, int, int, int, int]]

    def __init__(
            self,
            num_dice: int = 0,
            modifier: int = 0,
            rerolls: int = 0,
            weights: Optional[Tuple[int, int, int, int, int, int]] = None
    ):
        self.num_dice = num_dice
        self.modifier = modifier
        self.rerolls = rerolls
        self.weights = weights

    def resolve(self, force_result: Optional[int] = None) -> RollResult:
        result = RollResult(
            modifier=self.modifier, rerolls=self.rerolls, weights=self.weights
        )

        # If a result is being forced, contrive rolls to arrive at that number
        # Contrive to make them somewhat plausible
        if force_result:
            force_result -= self.modifier
            num_dice = self.num_dice

            # Add more dice if we can't get to the target (with a small margin
            # for plausibility)
            while num_dice * 6 < 1.2 * force_result:
                num_dice += 1

            # Remove dice if the only way to get close to the target is to roll
            # all 1's (minimum of one dice)
            while num_dice > 1 and num_dice * 1 > 0.8 * force_result:
                num_dice -= 1

            rolls = [random.randint(1, 6) for _ in range(num_dice)]
            while True:
                total = sum(rolls)
                if total > force_result:
                    can_be_lowered = [
                        idx for idx, roll in enumerate(rolls) if roll > 1
                    ]
                    if not can_be_lowered:
                        break
                    idx = random.choice(can_be_lowered)
                    rolls[idx] -= 1
                elif total < force_result:
                    can_be_raised = [
                        idx for idx, roll in enumerate(rolls) if roll < 6
                    ]
                    if not can_be_raised:
                        break
                    idx = random.choice(can_be_raised)
                    rolls[idx] += 1
                else:
                    break
            for roll in rolls:
                result.add_roll(roll)
        else:
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
    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        raise NotImplementedError

    def __str__(self):
        return f'{self.name} [{self.summary}]: {self.description}'


class AdderPrism(Prism):
    num_dice: int

    def __init__(self, name: str, description: str, num_dice: int):
        super().__init__(name, description)
        self.num_dice = num_dice

    @property
    def summary(self):
        return f'Adder, {self.num_dice}'

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        roll.num_dice += self.num_dice
        if param is not None:
            roll.num_dice += int(param)


class AbilityPrism(Prism):
    @property
    def summary(self):
        return f'Ability'

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        ability = param if param is not None else self.name
        roll.num_dice += character['abilities'][ability.lower()]


class BonusPrism(Prism):
    modifier: int

    def __init__(self, name: str, description: str, modifier: int):
        super().__init__(name, description)
        self.modifier = modifier

    @property
    def summary(self):
        return f'Bonus, {"+" if self.modifier > 0 else ""}{self.modifier}'

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        roll.modifier += self.modifier
        if param is not None:
            roll.modifier += int(param)


class MergerPrism(Prism):
    ability: str

    def __init__(self, name: str, description: str, ability: str):
        super().__init__(name, description)
        self.ability = ability

    @property
    def summary(self):
        return f'Merger, {self.ability}'

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        ability = param if param is not None else self.ability
        roll.num_dice += character['abilities'][ability.lower()]


class MultiplierPrism(Prism):
    multiplier: int

    def __init__(self, name: str, description: str, multiplier: int):
        super().__init__(name, description)
        self.multiplier = multiplier

    @property
    def summary(self):
        return f'Multiplier, x{self.multiplier}'

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        roll.num_dice = int(roll.num_dice * self.multiplier)
        if param is not None:
            roll.num_dice = int(roll.num_dice * int(param))


class OutputPrism(Prism):
    tier: int

    def __init__(self, name: str, description: str, tier: int):
        super().__init__(name, description)
        self.tier = tier

    @property
    def summary(self):
        return f'Output, Tier {self.tier}'

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        roll.rerolls += self.tier
        if param is not None:
            roll.rerolls += int(param)


class SpecialPrism(Prism):
    param_type: Optional[str]

    def __init__(
            self, name: str, description: str, param_type: Optional[str] = None
    ):
        super().__init__(name, description)
        self.param_type = param_type

    @property
    def summary(self):
        return f'Special'

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        if param is not None:
            if self.param_type == 'adder':
                roll.num_dice += int(param)
            elif self.param_type == 'bonus':
                roll.modifier += int(param)
            elif self.param_type == 'multiplier':
                roll.num_dice = int(roll.num_dice * int(param))
            elif self.param_type == 'merger':
                roll.num_dice += character['abilities'][param.lower()]
            else:
                raise ValueError(
                    f'Unexpected parameter to special prism {self.name}'
                )


class FakerPrism(SpecialPrism):
    pass


class WeighterPrism(SpecialPrism):
    def __init__(
            self, name: str, description: str, weights: List[int]
    ):
        super().__init__(name, description)
        self.weights = tuple(weights)

    def apply(
            self, character: Dict[str, Any], roll: Roll, param: Optional[Any]
    ) -> None:
        roll.weights = self.weights


PLUGIN = CharactersPlugin
