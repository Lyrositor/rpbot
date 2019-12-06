import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from random import randint
from typing import TYPE_CHECKING, Optional, Iterable, Any, Dict, Tuple

from discord import Message, PermissionOverwrite, Role, Member, TextChannel, \
    Guild
from discord.abc import GuildChannel

from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommandParam
from rpbot.state import State

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot

START_CMD = 'start'
END_CMD = 'end'
PLAYER_CMD = 'player'
OBSERVER_CMD = 'observer'
GM_CMD = 'gm'
MOVE_ALL_CMD = 'move_all'
MOVE_CMD = 'move'
MOVE_FORCE_CMD = 'move_force'
MOVE_RESET_CMD = 'move_reset'
ROLL_CMD = 'roll'
LOCK_CMD = 'lock'
UNLOCK_CMD = 'unlock'
REVEAL_CMD = 'reveal'


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

        self.register_command(
            name=START_CMD,
            handler=self.start_game,
            help_msg='Starts a new game in the server, replacing the current '
                     'one.',
            requires_admin=True,
            params=[
                PluginCommandParam('roleplay'), PluginCommandParam('players')
            ]
        )
        self.register_command(
            name=END_CMD,
            handler=self.end_game,
            help_msg='Ends the current game.',
            requires_admin=True
        )
        self.register_command(
            name=PLAYER_CMD,
            handler=self.mark_player,
            help_msg='Marks or unmarks a member as a player of the game.',
            requires_admin=True,
            params=[PluginCommandParam('user')]
        )
        self.register_command(
            name=OBSERVER_CMD,
            handler=self.mark_observer,
            help_msg='Marks or unmarks a member as an observer of the game.',
            requires_admin=True,
            params=[PluginCommandParam('user')]
        )
        self.register_command(
            name=GM_CMD,
            handler=self.mark_gm,
            help_msg='Marks or unmarks a member as a GM of the game.',
            requires_admin=True,
            params=[PluginCommandParam('user')]
        )
        self.register_command(
            name=MOVE_CMD,
            handler=self.move,
            help_msg='Moves you to a new location if specified, otherwise lists'
            ' available destinations.',
            requires_player=True,
            requires_room=True,
            params=[PluginCommandParam('location', True)]
        )
        self.register_command(
            name=MOVE_ALL_CMD,
            handler=self.move_all,
            help_msg='Marks or unmarks a member as an observer of the game.',
            requires_admin=True,
            params=[PluginCommandParam('room')]
        )
        self.register_command(
            name=MOVE_FORCE_CMD,
            handler=self.move_force,
            help_msg='Forces a player to move to the specified location.',
            requires_admin=True,
            params=[PluginCommandParam('room'), PluginCommandParam('user')]
        )
        self.register_command(
            name=MOVE_RESET_CMD,
            handler=self.move_reset,
            help_msg='Resets specified players\' cooldown.',
            requires_admin=True,
            params=[PluginCommandParam('user')]
        )
        self.register_command(
            name=ROLL_CMD,
            handler=self.roll_dice,
            help_msg='Rolls the specified number of d6s.',
            requires_player=False,
            requires_room=False,
            params=[PluginCommandParam('dice', True, 1, int)]
        )
        self.register_command(
            name=LOCK_CMD,
            handler=self.lock,
            help_msg='Locks a connection in the current room.',
            requires_admin=True,
            requires_room=True,
            params=[PluginCommandParam('location')]
        )
        self.register_command(
            name=UNLOCK_CMD,
            handler=self.unlock,
            help_msg='Unlocks a connection in the current room.',
            requires_admin=True,
            requires_room=True,
            params=[PluginCommandParam('location')]
        )
        self.register_command(
            name=REVEAL_CMD,
            handler=self.reveal,
            help_msg='Reveals an entrance to another location.',
            requires_admin=True,
            requires_room=True,
            params=[PluginCommandParam('location')]
        )

        if roleplay:
            for command in self.commands.values():
                command.enabled = command.name in roleplay.commands
            self.commands[START_CMD].enabled = False
        else:
            self.commands[START_CMD].enabled = True

    # noinspection PyUnusedLocal
    async def start_game(self, message: Message, roleplay: str, players: str):
        config = State.get_config(message.guild.id)
        if config and 'rp' in config and config['rp']:
            await message.channel.send(
                f'Cannot start roleplay, {config["rp"]} is already in progress.'
            )
            return

        if roleplay not in self.bot.roleplays:
            await message.channel.send(
                f'Cannot start roleplay, unknown roleplay name {roleplay}'
            )
            return

        loading_message = await message.channel.send(f'Setting up new game...')
        config = {'rp': roleplay, 'connections': {}}
        await self.bot.save_guild_config(message.guild, config)
        await self.bot.refresh_from_config(message.guild, config, True)
        await message.author.add_roles(State.get_admin_role(message.guild.id))

        self.roleplay = self.bot.roleplays[roleplay]
        player_role = State.get_player_role(message.guild.id)
        for member in message.mentions:
            await member.add_roles(player_role)
        await self.move_force(message, self.roleplay.starting_room, None)

        await message.channel.send(f'The game begins.')
        await loading_message.delete()
        await message.delete()

    async def end_game(self, message: Message):
        loading_message = await message.channel.send(f'Ending game...')
        config = {}
        guild: Guild = message.guild
        State.save_config(guild.id, config)
        State.save_plugins(guild.id, [])
        await self.bot.save_guild_config(guild, config)

        player_role = State.get_player_role(guild.id)
        observer_role = State.get_observer_role(guild.id)
        for player in player_role.members:
            await player.remove_roles(player_role)
            await player.add_roles(observer_role)

        await message.channel.send(f'The game ends.')
        await loading_message.delete()
        await message.delete()

        await self.bot.refresh_from_config(guild, config)

    # noinspection PyUnusedLocal
    async def mark_player(self, message: Message, user: str):
        await self._mark_with_role(
            message, State.get_player_role(message.guild.id), 'a player'
        )

    # noinspection PyUnusedLocal
    async def mark_observer(self, message: Message, user: str):
        await self._mark_with_role(
            message, State.get_observer_role(message.guild.id), 'an observer'
        )

    # noinspection PyUnusedLocal
    async def mark_gm(self, message: Message, user: str):
        await self._mark_with_role(
            message, State.get_admin_role(message.guild.id), 'an admin'
        )

    async def _mark_with_role(self, message: Message, role: Role, label: str):
        for member in message.mentions:
            toggle = await self._toggle_role(member, role)
            await message.channel.send(
                f'{member.mention} is '
                f'{"now" if toggle else "no longer"} {label}'
            )
        await message.delete()

    async def move(self, message: Message, room: Optional[str]):
        await message.delete()
        connections = State.get_config(message.guild.id)['connections']
        channel: TextChannel = message.channel
        destinations = self._list_destinations(connections, channel.name)

        if not room:
            destination_list = '\n'.join(
                destination + (' *(locked)*' if locked else '')
                for destination, locked in destinations
            )
            await channel.send(
                (
                    'The following destinations are available from here:\n'
                    + destination_list
                ) if destination_list
                else 'No destinations are currently available.',
                delete_after=60*60
            )
            return

        for destination, locked in destinations:
            if destination == room:
                if locked:
                    await channel.send(
                        f'{room} is currently locked off.',
                        delete_after=60*60
                    )
                    return
                break
        else:
            await channel.send(
                f'Cannot reach {room} from here.',
                delete_after=60*60
            )
            return

        move_timers = State.get_var(message.guild.id, 'move_timers')
        if not move_timers:
            move_timers = defaultdict(lambda: datetime.min)
        time_remaining = (
                move_timers[message.author.id] - datetime.now()
        ).total_seconds()
        if time_remaining > 0:
            minutes = time_remaining // 60
            await channel.send(
                'Must wait '
                + (
                    f'{int(minutes)} minutes' if minutes
                    else f'{int(time_remaining)} seconds'
                )
                + ' before moving again.',
                delete_after=60*60
            )
            return

        connection = self.roleplay.get_connection(channel.name, room)
        new_channel = await self._move_player(message.author, room)
        move_timers[message.author.id] = datetime.now() + timedelta(
            minutes=connection.timer
        )
        State.set_var(message.guild.id, 'move_timers', move_timers)
        await channel.send(f'{message.author.mention} moves to {room}')
        await new_channel.send(
            f'{message.author.mention} moves in from {channel.name}'
        )

    async def move_all(self, message: Message, room: str):
        for player in State.get_player_role(message.guild.id).members:
            await self._move_player(player, room)

    # noinspection PyUnusedLocal
    async def move_force(self, message: Message, room: str, user: Optional[str]):
        for player in message.mentions:
            await self._move_player(player, room)

    # noinspection PyUnusedLocal
    async def move_reset(self, message, user: Optional[str]):
        move_timers = State.get_var(message.guild.id, 'move_timers')
        if not move_timers:
            move_timers = defaultdict(lambda: datetime.min)
        for player in message.mentions:
            move_timers[player.id] = datetime.min
        State.set_var(message.guild.id, 'move_timers', move_timers)

    async def roll_dice(self, message: Message, num_dice: int):
        await message.delete()
        if num_dice < 1:
            await message.channel.send(
                'You need to specify a positive number of dice to roll.',
                delete_after=60*60
            )
            return
        if num_dice > 20:
            await message.channel.send(
                'You can only roll a maximum of 20 dice.',
                delete_after=60*60
            )
            return
        results = []
        total = 0
        for i in range(num_dice):
            result = randint(1, 6)
            total += result
            results.append(self.NUMBERS_EMOJI[result])
        await message.channel.send(
            f'{message.author.mention} rolled **{total}**: '
            + ' '.join(results)
        )

    async def lock(self, message: Message, location: str):
        await self._lock_or_unlock(message, location, True)

    async def unlock(self, message: Message, location: str):
        await self._lock_or_unlock(message, location, False)

    async def reveal(self, message: Message, location: str):
        config = State.get_config(message.guild.id)
        channel: TextChannel = message.channel
        connection = self.roleplay.get_connection(channel.name, location)
        if not connection:
            await channel.send(
                f'No connection from {channel.name} to {location}.'
            )
            return

        if not connection.hidden:
            await channel.send(
                f'Connection from {channel.name} to {location} is already '
                'revealed.'
            )
        else:
            config['connections'][connection.name]['h'] = False
            State.save_config(message.guild.id, config)
            await self.bot.save_guild_config(message.guild, config)
            await channel.send(
                f'A connection between {channel.name} and {location} has been '
                'revealed.'
            )
            await message.delete()

    async def _lock_or_unlock(
            self, message: Message, location: str, lock: bool = True
    ):
        config = State.get_config(message.guild.id)
        channel: TextChannel = message.channel
        connection = self.roleplay.get_connection(channel.name, location)
        if not connection:
            await channel.send(
                f'No connection from {channel.name} to {location}.'
            )
            return
        locked = config['connections'][connection.name]['l']
        if locked and lock or not locked and not lock:
            await channel.send(
                f'Access to {location} is already '
                f'{"locked" if lock else "unlocked"}.'
            )
            return
        self._update_connection(
            config["connections"], channel.name, location, locked=lock
        )
        State.save_config(message.guild.id, config)
        await self.bot.save_guild_config(message.guild, config)
        await channel.send(
            f'{"Locked" if lock else "Unlocked"} access to {location}.'
        )
        await message.delete()

    def _list_destinations(
            self, connections: Dict[str, Dict[str, Any]], room: str
    ) -> Iterable[Tuple[str, bool]]:
        for connection in self.roleplay.connections:
            state = connections[connection.name]
            if state['h']:
                continue
            if room == connection.room1:
                yield (connection.room2, state['l'])
            elif room == connection.room2:
                yield (connection.room1,  state['l'])

    def _update_connection(
            self,
            connections: Dict[str, Dict[str, Any]],
            room1: str,
            room2: str,
            locked: Optional[bool] = None,
            hidden: Optional[bool] = None
    ):
        connection = self.roleplay.get_connection(room1, room2)
        connection_config = connections[connection.name]
        if locked is not None:
            connection_config['l'] = locked
        if hidden is not None:
            connection_config['h'] = hidden

    async def _move_player(
            self, player: Member, dest_room: str
    ) -> Optional[GuildChannel]:
        clear_permissions = []
        for room in self.roleplay.rooms:
            room_channel = self.find_channel_by_name(
                player.guild, room, self.roleplay.rooms[room].section
            )
            # noinspection PyTypeChecker
            clear_permissions.append(
                room_channel.set_permissions(player, overwrite=None)
            )
        await asyncio.wait(clear_permissions)
        new_channel = self.find_channel_by_name(
            player.guild, dest_room, self.roleplay.rooms[dest_room].section
        )
        await new_channel.set_permissions(
            player,
            read_messages=True,
            send_messages=True
        )
        return new_channel

    @staticmethod
    async def _toggle_role(member: Member, role: Role) -> bool:
        if role.id in (r.id for r in member.roles):
            await member.remove_roles(role)
            return False
        else:
            await member.add_roles(role)
            return True
