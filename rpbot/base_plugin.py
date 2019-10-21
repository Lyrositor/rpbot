import json
from random import randint
from typing import TYPE_CHECKING

from discord import Message, PermissionOverwrite

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
            True,
            [
                PluginCommandParam('roleplay')
            ]
        )
        self.commands['roll'] = PluginCommand(
            'roll',
            self.roll_dice,
            'Rolls the specified number of d6s.',
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
        self.bot.refresh_from_config(message.guild.id, config)

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
