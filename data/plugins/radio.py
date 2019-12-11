from typing import TYPE_CHECKING

from discord import Message, Guild, PermissionOverwrite, CategoryChannel

from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommandParam

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot

RADIO_CMD = 'radio'
RADIO_SETUP_CMD = 'radio_setup'

RADIO_CHANNEL = 'radio'


class RadioPlugin(Plugin):
    def __init__(self, bot: 'RoleplayBot', roleplay: Roleplay):
        super().__init__(bot, roleplay)

        self.register_command(
            name=RADIO_SETUP_CMD,
            handler=self.radio_setup,
            help_msg='Creates all the radio channels.',
            requires_admin=True
        )
        self.register_command(
            name=RADIO_CMD,
            handler=self.radio,
            help_msg='Moves you to a new location if specified, otherwise lists'
            ' available destinations.',
            requires_player=True,
            requires_room=True,
            params=[PluginCommandParam('text')]
        )

        if roleplay:
            for command in self.commands.values():
                command.enabled = command.name in roleplay.commands

    async def radio_setup(self, message: Message):
        guild: Guild = message.guild
        sections = {r.section for r in self.roleplay.rooms.values()}
        for section in sections:
            for category in guild.categories:
                if category.name == section:
                    break
            else:
                category = guild.create_category(section)
            for channel in category.text_channels:
                if channel.name == RADIO_CHANNEL:
                    break
            else:
                await category.create_text_channel(
                    RADIO_CHANNEL,
                    overwrites={
                        guild.default_role: PermissionOverwrite(
                            send_messages=False,
                        )
                    }
                )

    async def radio(self, message: Message, text: str):
        # Only broadcast within the same channel category
        category: CategoryChannel = message.channel.category
        if not category:
            return

        for channel in category.text_channels:
            if channel.name == RADIO_CHANNEL:
                await channel.send(text)

        await message.channel.send(
            f'{message.author.mention} sends out a radio message.'
        )
        await message.delete()


PLUGIN = RadioPlugin
