from random import randint
from typing import TYPE_CHECKING, Optional, Iterable, Any, Dict, Tuple

from discord import Message, PermissionOverwrite, Role, Member, TextChannel

from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommand, PluginCommandParam
from rpbot.state import State

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot

START_CMD = 'start'
PLAYER_CMD = 'player'
OBSERVER_CMD = 'observer'
GM_CMD = 'gm'
MOVE_ALL_CMD = 'move_all'
MOVE_CMD = 'move'
MOVE_FORCE_CMD = 'move_force'
ROLL_CMD = 'roll'


class BasePlugin(Plugin):
    NUMBERS_EMOJI = {
        1: ':one:',
        2: ':two:',
        3: ':three:',
        4: ':four:',
        5: ':five:',
        6: ':six:',
    }

    def __init__(self, bot: 'RoleplayBot', roleplay: Roleplay):
        super().__init__(bot, roleplay)

        self.commands[START_CMD] = PluginCommand(
            START_CMD, self.start_game,
            'Starts a new game in the server, replacing the current one.',
            False, True, False, [PluginCommandParam('roleplay')]
        )
        # TODO Add end and reset commands
        self.commands[PLAYER_CMD] = PluginCommand(
            PLAYER_CMD, self.mark_player,
            'Marks or unmarks a member as a player of the game.',
            False, True, False, [PluginCommandParam('user')]
        )
        self.commands[OBSERVER_CMD] = PluginCommand(
            OBSERVER_CMD, self.mark_observer,
            'Marks or unmarks a member as an observer of the game.',
            False, True, False, [PluginCommandParam('user')]
        )
        self.commands[GM_CMD] = PluginCommand(
            GM_CMD, self.mark_gm,
            'Marks or unmarks a member as a GM of the game.',
            False, True, False, [PluginCommandParam('user')]
        )
        self.commands[MOVE_ALL_CMD] = PluginCommand(
            MOVE_ALL_CMD, self.move_all,
            'Marks or unmarks a member as an observer of the game.',
            False, True, False, [PluginCommandParam('room')]
        )
        self.commands[MOVE_CMD] = PluginCommand(
            MOVE_CMD, self.move,
            'Moves you to a new location if specified, otherwise lists '
            'available destinations.',
            True, False, True, [PluginCommandParam('room', True)]
        )
        self.commands[MOVE_FORCE_CMD] = PluginCommand(
            MOVE_FORCE_CMD, self.move_force,
            'Forces a player to move to the specified location.',
            False, True, False,
            [PluginCommandParam('room'), PluginCommandParam('user')]
        )
        # TODO Add a move_force command
        self.commands[ROLL_CMD] = PluginCommand(
            ROLL_CMD, self.roll_dice,
            'Rolls the specified number of d6s.',
            True, False, True, [PluginCommandParam('dice', True, 1, int)]
        )

        for command in self.commands.values():
            if command.name not in roleplay.commands:
                command.enabled = True

    async def start_game(self, message: Message, roleplay: str):
        config = State.get_config(message.guild.id)
        if config and 'rp' in config and config['rp']:
            await message.channel.send(
                f'Cannot start roleplay, {config["rp"]} is already in progress.'
            )
            return

        config = {
            'rp': roleplay,
            'connections': {}
        }
        self.bot.save_guild_config(message.guild, config)
        self.bot.refresh_from_config(message.guild, config)
        await message.author.add_role(State.get_admin_role(message.guild.id))
        await message.delete()

    # noinspection PyUnusedLocal
    async def mark_player(self, message: Message, user: str):
        player_role = State.get_player_role(message.guild.id)
        for member in message.mentions:
            toggle = await self._toggle_role(member, player_role)
            await message.channel.send(
                f'{member.mention} is '
                f'{"now" if toggle else "no longer"} a player'
            )
        await message.delete()

    # noinspection PyUnusedLocal
    async def mark_observer(self, message: Message, user: str):
        observer_role = State.get_observer_role(message.guild.id)
        for member in message.mentions:
            toggle = await self._toggle_role(member, observer_role)
            await message.channel.send(
                f'{member.mention} is '
                f'{"now" if toggle else "no longer"} an observer'
            )
        await message.delete()

    # noinspection PyUnusedLocal
    async def mark_gm(self, message: Message, user: str):
        gm_role = State.get_admin_role(message.guild.id)
        for member in message.mentions:
            toggle = await self._toggle_role(member, gm_role)
            await message.channel.send(
                f'{member.mention} is '
                f'{"now" if toggle else "no longer"} a GM'
            )
        await message.delete()

    async def move_all(self, message: Message, room: str):
        for player in State.get_player_role(message.guild.id).members:
            await self._move_player(player, room)

    async def move(self, message: Message, room: Optional[str]):
        connections = State.get_config(message.guild.id)['connections']
        channel: TextChannel = message.channel
        destinations = self._list_destinations(connections, channel.name)

        if not room:
            destination_list = '\n'.join(
                d[0] + (' *(locked)*' if d[1] else '') for d in destinations
            )
            await channel.send(
                (
                    'The following destinations are available from here:\n'
                    + destination_list
                ) if destination_list
                else 'No destinations are currently available.'
            )
            return

        for destination, locked in destinations:
            if destination == room:
                if locked:
                    await channel.send(f'{room} is currently locked off.')
                    return
                break
        else:
            await channel.send(f'Cannot reach {room} from here.')
            return

        await self._move_player(message.author, room)
        await channel.send(f'{message.author.mention} moves to {room}')
        await message.delete()

    # noinspection PyUnusedLocal
    async def move_force(self, message: Message, room: str, user: str):
        for player in message.mentions:
            await self._move_player(player, room)  # TODO Fix

    async def roll_dice(self, message: Message, num_dice: int):
        if num_dice < 1:
            await message.channel.send(
                'You need to specify a positive number of dice to roll.'
            )
            return
        results = []
        for i in range(num_dice):
            results.append(self.NUMBERS_EMOJI[randint(1, 6)])
        await message.channel.send(
            f'{message.author.mention} rolled: ' + ' '.join(results)
        )

    def _list_destinations(
            self, connections: Dict[str, Dict[str, Any]], room: str
    ) -> Iterable[Tuple[str, bool]]:
        for connection in self.roleplay.connections:
            state = connections[connection.name]
            if state['hidden']:
                continue
            if room == connection.room1:
                yield (connection.room2, state['locked'])
            elif room == connection.room2:
                yield (connection.room1 + state['locked'])

    async def _move_player(self, player: Member, dest_room: str):
        for room in self.roleplay.rooms:
            room_channel = self.find_channel_by_name(
                player.guild, room, self.roleplay.rooms[room].section
            )
            # noinspection PyTypeChecker
            await room_channel.set_permissions(player, overwrite=None)
        new_channel = self.find_channel_by_name(
            player.guild, dest_room, self.roleplay.rooms[dest_room].section
        )
        await new_channel.set_permissions(
            player,
            overwrite=PermissionOverwrite(read_messages=True)
        )

    @staticmethod
    async def _toggle_role(member: Member, role: Role) -> bool:
        if role.id in (r.id for r in member.roles):
            await member.remove_roles(role)
            return False
        else:
            await member.add_roles(role)
            return True
