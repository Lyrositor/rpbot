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
            f'`[{channel.name if channel else "???"}]` **{name}** moves to **{room}**'
        )

    async def log_announcement(self, message: str) -> None:
        formatted_message = ''
        for line in message.split('\n'):
            formatted_message += f'> {line}\n'
        await self.log(formatted_message.strip())

    async def log_roll(
            self, name: str, channel: TextChannel, roll: int
    ) -> None:
        await self.log(f'`[{channel.name}]` **{name}** rolls **{roll}**')

    async def log_from_channel(self, channel: TextChannel, message: str) -> None:
        await self.log(f"`[{channel.name}]` {message}")

    async def log(self, message: str) -> None:
        for channel in self.guild.text_channels:
            if channel.name == self.channel_name:
                await channel.send(message[:MAX_MESSAGE_LENGTH])
                if message[MAX_MESSAGE_LENGTH:]:
                    await channel.send(message[MAX_MESSAGE_LENGTH:])
                break
