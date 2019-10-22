import json
from random import randint
from typing import TYPE_CHECKING

from discord import Message, PermissionOverwrite, Role, Member

from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommand, PluginCommandParam
from rpbot.state import State

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot


class BasePlugin(Plugin):
    BOT_CONFIG_CHANNEL = 'rpbot-config'

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

        self.commands['start'] = PluginCommand(
            'start',
            self.start_game,
            'Starts a new game in the server, replacing the current one.',
            False,
            True,
            [
                PluginCommandParam('roleplay')
            ]
        )
        self.commands['player'] = PluginCommand(
            'player',
            self.mark_player,
            'Marks or unmarks a member as a player of the game.',
            False,
            True,
            [
                PluginCommandParam('user')
            ]
        )
        self.commands['observer'] = PluginCommand(
            'observer',
            self.mark_observer,
            'Marks or unmarks a member as an observer of the game.',
            False,
            True,
            [
                PluginCommandParam('user')
            ]
        )
        self.commands['gm'] = PluginCommand(
            'gm',
            self.mark_gm,
            'Marks or unmarks a member as a GM of the game.',
            False,
            True,
            [
                PluginCommandParam('user')
            ]
        )
        self.commands['move_all'] = PluginCommand(
            'move_all',
            self.move_all,
            'Marks or unmarks a member as an observer of the game.',
            False,
            True,
            [
                PluginCommandParam('room')
            ]
        )
        self.commands['move'] = PluginCommand(
            'move',
            self.move,
            'Moves you to a new location if specified, otherwise lists '
            'available destinations.',
            True,
            False,
            [
                PluginCommandParam('room')
            ]
        )
        # TODO Add a move_force command
        self.commands['roll'] = PluginCommand(
            'roll',
            self.roll_dice,
            'Rolls the specified number of d6s.',
            True,
            False,
            [
                PluginCommandParam('dice', True, 1, int)
            ]
        )

    async def start_game(self, message: Message, roleplay: str):
        config = State.get_config(message.guild.id)
        if config and 'rp' in config and config['rp']:
            await message.channel.send(
                f'Cannot start roleplay, {config["rp"]} is already in progress.'
            )
            return

        for channel in message.guild.text_channels:
            if channel.name == self.BOT_CONFIG_CHANNEL:
                config_channel = channel
                break
        else:
            config_channel = await message.guild.create_text_channel(
                self.BOT_CONFIG_CHANNEL,
                overwrites={
                    message.guild.default_role: PermissionOverwrite(
                        read_messages=False
                    )
                }
            )
        config = {
            'rp': roleplay
        }
        json_config = json.dumps(config, indent=2)
        await config_channel.send(f'```json\n{json_config}```')
        self.bot.refresh_from_config(message.guild, config)
        await message.author.add_role(State.get_admin_role(message.guild.id))
        await message.delete()

    async def mark_player(self, message: Message, user: str):
        player_role = State.get_player_role(message.guild.id)
        for member in message.mentions:
            toggle = await self._toggle_role(member, player_role)
            await message.channel.send(
                f'{member.mention} is '
                f'{"now" if toggle else "no longer"} a player'
            )
        await message.delete()

    async def mark_observer(self, message: Message, user: str):
        observer_role = State.get_observer_role(message.guild.id)
        for member in message.mentions:
            toggle = await self._toggle_role(member, observer_role)
            await message.channel.send(
                f'{member.mention} is '
                f'{"now" if toggle else "no longer"} an observer'
            )
        await message.delete()

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
        pass

    async def move(self, message: Message, room: str):
        pass

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

    @staticmethod
    async def _toggle_role(member: Member, role: Role) -> bool:
        if role.id in (r.id for r in member.roles):
            await member.remove_roles(role)
            return False
        else:
            await member.add_roles(role)
            return True
