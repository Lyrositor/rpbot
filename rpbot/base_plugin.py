import asyncio
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta
from random import randint
from typing import TYPE_CHECKING, Optional, Iterable, Any, Dict, Tuple

from discord import Message, Role, Member, TextChannel, Guild

from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommandParam, delete_message
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
FATE_CMD = 'fate'
LOCK_CMD = 'lock'
UNLOCK_CMD = 'unlock'
REVEAL_CMD = 'reveal'
HIDE_CMD = 'hide'
KEY_CMD = 'key'
RELOAD_CMD = 'reload'
ANNOUNCE_CMD = 'a'
VIEW_ADD_CMD = 'viewadd'
VIEW_REMOVE_CMD = 'viewremove'
VIEW_LIST_CMD = 'viewlist'


class BasePlugin(Plugin):
    FATE_EMOJI = {
        -1: ':heavy_minus_sign:',
        0: ':black_square_button:',
        1: ':heavy_plus_sign:'
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
            help_msg='Moves all players to a location.',
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
            help_msg='Rolls the specified number of polyhedral dice in standard notation (2d4, 3d10...). If the number '
                     'of sides is not specified, it defaults to 6.',
            requires_player=False,
            requires_room=False,
            params=[PluginCommandParam('dice', True, "1")]
        )
        self.register_command(
            name=FATE_CMD,
            handler=self.roll_dice_fate,
            help_msg='Rolls the specified number of FATE dice.',
            requires_player=False,
            requires_room=False,
            params=[PluginCommandParam('dice', True, 1, int)]
        )
        self.register_command(
            name=LOCK_CMD,
            handler=self.lock,
            help_msg='Locks a connection in the current room. Requires a key.',
            requires_room=True,
            params=[PluginCommandParam('location')]
        )
        self.register_command(
            name=UNLOCK_CMD,
            handler=self.unlock,
            help_msg=
            'Unlocks a connection in the current room. Requires a key.',
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
        self.register_command(
            name=HIDE_CMD,
            handler=self.hide,
            help_msg='Hides an entrance to another location.',
            requires_admin=True,
            requires_room=True,
            params=[PluginCommandParam('location')]
        )
        self.register_command(
            name=KEY_CMD,
            handler=self.toggle_key,
            help_msg='Gives or takes a key from a player.',
            requires_admin=True,
            params=[
                PluginCommandParam('room1'),
                PluginCommandParam('room2'),
                PluginCommandParam('user')
            ]
        )
        self.register_command(
            name=RELOAD_CMD,
            handler=self.reload,
            help_msg='Reloads the roleplay from its YAML definition.',
            requires_admin=True,
            params=[]
        )
        self.register_command(
            name=ANNOUNCE_CMD,
            handler=self.announce,
            help_msg='Announces a message to players. This is how GMs should '
                     'usually write narration.',
            requires_admin=True,
            params=[PluginCommandParam('text')]
        )
        self.register_command(
            name=VIEW_ADD_CMD,
            handler=self.view_add,
            help_msg=(
                'Adds a remote view to another room inside this channel.'
            ),
            requires_admin=True,
            params=[PluginCommandParam('room')]
        )
        self.register_command(
            name=VIEW_REMOVE_CMD,
            handler=self.view_remove,
            help_msg='Removes a remote view on another room from this channel.',
            requires_admin=True,
            params=[PluginCommandParam('room')]
        )
        self.register_command(
            name=VIEW_LIST_CMD,
            handler=self.view_list,
            help_msg='Lists all active remote views.',
            requires_admin=True,
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
            await message.delete()
            return

        for destination, locked in destinations:
            if destination == room:
                if locked:
                    await channel.send(
                        f'{room} is currently locked off.',
                        delete_after=60*60
                    )
                    await message.delete()
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
        new_channel = await self._move_player(
            message.author, room, message.channel
        )
        move_timers[message.author.id] = datetime.now() + timedelta(
            minutes=connection.timer
        )
        State.set_var(message.guild.id, 'move_timers', move_timers)
        await channel.send(f'{message.author.mention} moves to {room}')
        await new_channel.send(
            f'{message.author.mention} moves in from {channel.name}'
        )
        await message.delete()

    async def move_all(self, message: Message, room: str):
        for player in State.get_player_role(message.guild.id).members:
            await self._move_player(player, room)

    # noinspection PyUnusedLocal
    async def move_force(
            self, message: Message, room: str, user: Optional[str]
    ):
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

    async def roll_dice_fate(self, message: Message, num_dice: int):
        await message.delete()
        if num_dice < 1:
            await message.channel.send(
                'You need to specify a positive number of dice to roll.',
                delete_after=60 * 60
            )
            return
        if num_dice > 20:
            await message.channel.send(
                'You can only roll a maximum of 20 dice.',
                delete_after=60 * 60
            )
            return
        results = []
        total = 0
        for i in range(num_dice):
            result = randint(-1, 1)
            total += result
            results.append(self.FATE_EMOJI[result])
        await message.channel.send(
            f'{message.author.mention} rolled **{total}**: '
            + ' '.join(results)
        )
        await self.bot.get_chronicle(message.guild).log_roll(
            message.author.mention, message.channel, total
        )

    @delete_message
    async def roll_dice(self, message: Message, dice: str = "1") -> Optional[str]:
        elements = re.split(r'\s+', dice.strip())
        rolls = []
        for element in elements:
            match = re.match(r'^(\d+)(?:d(\d+))?$', element)
            if not match:
                await message.channel.send(f'Invalid roll request: {dice}')
                return
            num_dice, num_sides = int(match.group(1)), int(match.group(2) or "6")
            for _ in range(num_dice):
                # Special case for the d100
                if num_sides == 100:
                    rolls.append((random.randint(0, num_sides - 1), num_sides))
                else:
                    rolls.append((random.randint(1, num_sides), num_sides))
        roll_results = " + ".join(
            (str(roll).zfill(2) if num_sides == 100 else str(roll)) + f" [d{num_sides}]" for roll, num_sides in rolls
        )
        total = sum(roll for roll, num_sides in rolls)
        if len(rolls) == 1:
            roll_message = f'rolled {roll_results}'
        else:
            roll_message = f'rolled **{total}** = {roll_results}'
        await message.channel.send(f'{message.author.mention} {roll_message}')
        await self.bot.get_chronicle(message.guild).log_roll(
            message.author.mention, message.channel, total
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
                f'No connection from {channel.name} to {location}.',
                delete_after=60*60
            )
            return

        is_hidden = config['connections'][connection.name].get('h', False)
        if not is_hidden:
            await channel.send(
                f'Connection from {channel.name} to {location} is already '
                'revealed.',
                delete_after=60*60
            )
        else:
            config['connections'][connection.name]['h'] = False
            State.save_config(message.guild.id, config)
            await self.bot.save_guild_config(message.guild, config)
            text = f'A connection between {channel.name} and {location} has ' \
                   f'been revealed.'
            await channel.send(text)
            await message.delete()
            await self.bot.get_chronicle(message.guild).log_announcement(
                channel, text
            )

    async def hide(self, message: Message, location: str):
        config = State.get_config(message.guild.id)
        channel: TextChannel = message.channel
        connection = self.roleplay.get_connection(channel.name, location)
        if not connection:
            await channel.send(
                f'No connection from {channel.name} to {location}.',
                delete_after=60*60
            )
            return

        is_hidden = config['connections'][connection.name].get('h', False)
        if is_hidden:
            await channel.send(
                f'Connection from {channel.name} to {location} is already '
                'hidden.',
                delete_after=60*60
            )
        else:
            config['connections'][connection.name]['h'] = True
            State.save_config(message.guild.id, config)
            await self.bot.save_guild_config(message.guild, config)
            text = f'A connection between {channel.name} and {location} has ' \
                   f'been hidden.'
            await channel.send(text)
            await message.delete()
            await self.bot.get_chronicle(message.guild).log_announcement(
                channel, text
            )

    # noinspection PyUnusedLocal
    async def toggle_key(
            self, message: Message, room1: str, room2: str, user: str
    ):
        connection = self.roleplay.get_connection(room1, room2)
        if not connection:
            await message.channel.send(
                f'No connection from {room1} to {room2}.'
            )
            return

        config = State.get_config(message.guild.id)
        keys = config['connections'][connection.name]['k']
        for member in message.mentions:
            if member.id not in keys:
                keys.append(member.id)
                await message.channel.send(
                    f'{member.mention} can now lock and unlock the connection '
                    f'from {room1} to {room2}.'
                )
            else:
                keys.remove(member.id)
                await message.channel.send(
                    f'{member.mention} can no longer lock and unlock the '
                    f'connection from {room1} to {room2}.'
                )
        State.save_config(message.guild.id, config)
        await self.bot.save_guild_config(message.guild, config)
        await message.delete()

    async def reload(self, message: Message) -> None:
        self.bot.reload()
        await self.bot.refresh_from_config(
            message.guild, State.get_config(message.guild.id)
        )
        await message.channel.send('Roleplay definition and plugins reloaded.')

    @delete_message
    async def announce(self, message: Message, text: str) -> None:
        formatted_message = ''
        for line in text.split('\n'):
            formatted_message += f'> {line}\n'
        await message.channel.send(formatted_message.strip())
        await self.bot.get_chronicle(message.guild).log_announcement(
            message.channel, text
        )

    @delete_message
    async def view_add(self, message: Message, room: str) -> None:
        config = State.get_config(message.guild.id)
        if 'views' not in config:
            config['views'] = {}
        if room not in config['views']:
            config['views'][room] = []
        if message.channel.name not in config['views'][room]:
            config['views'][room].append(message.channel.name)
            await self.bot.save_guild_config(message.guild, config)
            await message.channel.send(f'Remote view to {room} added.')
        else:
            await message.channel.send(
                f'There is already a remote view to {room} in this channel.'
            )

    @delete_message
    async def view_remove(self, message: Message, room: str) -> None:
        config = State.get_config(message.guild.id)
        if 'views' not in config:
            config['views'] = {}
        if room in config['views'] \
                and message.channel.name in config['views'][room]:
            config['views'][room].remove(message.channel.name)
            await self.bot.save_guild_config(message.guild, config)
            await message.channel.send(f'Remote view to {room} removed.')
        else:
            await message.channel.send(
                f'No remote view to {room} set up in this channel.'
            )

    @delete_message
    async def view_list(self, message: Message) -> None:
        config = State.get_config(message.guild.id)
        all_views = []
        for user_id, views in config.get('views', {}).items():
            user: Member = message.guild.get_member(user_id)
            if user and views:
                all_views.append(
                    f'**{user.display_name}:** ' + ', '.join(views)
                )
        if all_views:
            await message.channel.send(
                'The following remote views are set up:\n'
                + '\n'.join(all_views)
            )
        else:
            await message.channel.send('No remote views are set up.')

    async def _lock_or_unlock(
            self, message: Message, location: str, lock: bool = True
    ):
        config = State.get_config(message.guild.id)
        channel: TextChannel = message.channel
        connection = self.roleplay.get_connection(channel.name, location)
        if not connection:
            await channel.send(
                f'No connection from {channel.name} to {location}.',
                delete_after=60*60
            )
            return
        connection_config = config['connections'][connection.name]

        if not State.is_admin(message.author) \
                and message.author.id not in connection_config['k']:
            await channel.send(
                f'{message.author.mention} does not have the key to '
                f'{location}.',
                delete_after=60*60
            )
            return

        locked = connection_config['l']
        if locked and lock or not locked and not lock:
            await channel.send(
                f'Access to {location} is already '
                f'{"locked" if lock else "unlocked"}.',
                delete_after=60*60
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
        name = 'the GM' \
            if State.is_admin(message.author) else message.author.display_name
        await self.bot.get_chronicle(message.guild).log_announcement(
            channel,
            f'Access from **{message.channel.name}** to **{location}** '
            f'{"" if lock else "un"}locked by **{name}**'
        )

    def _list_destinations(
            self, connections: Dict[str, Dict[str, Any]], room: str
    ) -> Iterable[Tuple[str, bool]]:
        for connection in self.roleplay.connections:
            state = connections[connection.name]
            if state['h']:
                continue
            if room == connection.room1:
                yield connection.room2, state['l']
            elif room == connection.room2:
                yield connection.room1,  state['l']

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
            self,
            player: Member,
            dest_room: str,
            from_channel: Optional[TextChannel] = None
    ) -> Optional[TextChannel]:
        if from_channel:
            await from_channel.set_permissions(player, overwrite=None)
        else:
            clear_permissions = []
            for name, room in self.roleplay.rooms.items():
                room_channel = self.find_channel_by_name(
                    player.guild, name, room.section
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
            read_messages=True
        )
        await self.bot.get_chronicle(player.guild).log_movement(
            player.display_name, dest_room, from_channel
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
