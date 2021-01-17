from typing import Optional

from discord import Member, TextChannel, Guild

from rpbot.state import State
from rpbot.utils import MAX_MESSAGE_LENGTH


class Chronicle:
    channel_name: str

    def __init__(self, guild: Guild, channel_name: str):
        self.guild = guild
        self.channel_name = channel_name

    async def log_player_message(
            self,
            member: Member,
            channel: TextChannel,
            message: str
    ) -> None:
        formatted_message = message.strip()
        if message.startswith('>'):
            formatted_message = '\n' + formatted_message
        await self.log_from_channel(
            channel, f'**{member.display_name}**: {formatted_message}'
        )

    async def log_movement(
            self, name: str, room: str, channel: Optional[TextChannel] = None
    ) -> None:
        await self.log(
            room,
            f'`[{channel.name if channel else "???"}]` '
            f'**{name}** moves to **{room}**'
        )

    async def log_announcement(
            self, channel: Optional[TextChannel], message: str
    ) -> None:
        formatted_message = ''
        for line in message.split('\n'):
            formatted_message += f'> {line}\n'
        await self.log(
            channel.name if channel else None, formatted_message.strip()
        )

    async def log_roll(
            self, name: str, channel: TextChannel, roll: int
    ) -> None:
        await self.log(
            channel.name, f'`[{channel.name}]` **{name}** rolls **{roll}**'
        )

    async def log_from_channel(self, channel: TextChannel, message: str) -> None:
        await self.log(channel.name, f"`[{channel.name}]` {message}")

    async def log(self, source_channel: Optional[str], message: str) -> None:
        config = State.get_config(self.guild.id)
        if not config:
            return
        views = config.get('views', {})
        dest_channels = {self.channel_name}
        if source_channel in views:
            dest_channels.update(views[source_channel])
        for channel in self.guild.text_channels:
            if channel.name in dest_channels:
                await channel.send(message[:MAX_MESSAGE_LENGTH])
                if message[MAX_MESSAGE_LENGTH:]:
                    await channel.send(message[MAX_MESSAGE_LENGTH:])
