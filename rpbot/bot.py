import importlib.util
import json
import logging
import os
import sys
from asyncio import BaseEventLoop
from glob import glob
from typing import List, Dict, Type, Any, Optional, Union

import discord
import yaml
from discord import Client, CategoryChannel, TextChannel, PermissionOverwrite, \
    Guild, Message, NotFound, Color, Forbidden, Intents, Reaction, User, Member

from rpbot.base_plugin import BasePlugin
from rpbot.chronicle import Chronicle
from rpbot.data.connection import Connection
from rpbot.data.role import Role
from rpbot.data.roleplay import Roleplay
from rpbot.data.room import Room
from rpbot.plugin import Plugin, PluginCommand
from rpbot.state import State
from rpbot.utils import reply


class RoleplayBot(Client):
    BOT_CONFIG_CHANNEL = 'rpbot-config'
    CHRONICLE_CHANNEL = 'chronicle'

    def __init__(
            self,
            plugins_dir: str,
            roleplays_dir: str,
            admins: List[str],
            loop: Optional[BaseEventLoop] = None
    ):
        intents = Intents.default()
        intents.members = True
        super().__init__(intents=intents, loop=loop)

        self.admins = admins
        self.plugins_dir = plugins_dir
        self.roleplays_dir = roleplays_dir
        self.plugins = {}
        self.roleplays = {}
        self.chronicles = {}
        self.reload()

    def reload(self) -> None:
        self.plugins = self.load_plugins(self.plugins_dir)
        self.roleplays = self.load_roleplays(self.roleplays_dir)

    def run(self, token: str) -> None:
        super().run(token)

    async def on_ready(self):
        for guild in self.guilds:
            for channel in guild.channels:
                if channel.name == self.BOT_CONFIG_CHANNEL \
                        and isinstance(channel, TextChannel) \
                        and channel.last_message_id is not None:
                    # noinspection PyBroadException
                    try:
                        config_messages = await channel.history(
                            limit=20, oldest_first=False
                        ).flatten()
                        config_json = ''
                        for config_message in config_messages:
                            message_json = config_message.content[4:-3]
                            if message_json.startswith('^'):
                                config_json = message_json[1:] + config_json
                            else:
                                config_json = message_json + config_json
                                break
                        config = json.loads(config_json)
                        await self.refresh_from_config(guild, config)
                    except NotFound:
                        logging.warning(
                            'No config message found, ignoring guild'
                        )
                    except json.JSONDecodeError as e:
                        logging.error(e)
                        logging.warning('Config is invalid, ignoring guild')
                    except Exception:
                        logging.exception(
                            'Encountered unexpected error while setting up'
                        )
                        sys.exit(1)
                    finally:
                        break
            await self.get_chronicle(guild).log_announcement(
                None,
                "[Bot restarted, some messages may have been lost]"
            )

        logging.info('Setup complete')

    async def on_message(self, message: Message):
        # Ignore all DMs
        if message.guild is None:
            return

        # Ignore all messages from this bot
        if message.author == self.user:
            return

        plugins = self.get_all_plugins(message.guild)

        # Do a special case for !help, since we need an overview of all plugins
        # to make it complete
        if message.clean_content == PluginCommand.PREFIX + 'help':
            help_message = '\n'.join(
                p.get_help(State.is_admin(message.author)) for p in plugins
            )
            if not help_message:
                help_message = 'No commands are currently available.'
            else:
                help_message = \
                    'The following commands are currently available:\n' \
                    + help_message
            await reply(message, help_message)
            return

        for plugin in plugins:
            if await plugin.process_message(message):
                break
        else:
            roleplay = self.get_roleplay_for_guild(message.guild.id)
            if roleplay and message.channel.name in roleplay.rooms:
                await self.get_chronicle(message.guild).log_player_message(
                    message.author, message.channel, message.clean_content
                )

    async def on_reaction_add(
            self, reaction: Reaction, user: Union[Member, User]
    ) -> None:
        plugins = self.get_all_plugins(reaction.message.guild)
        for plugin in plugins:
            if await plugin.process_react(reaction, user):
                break

    def get_chronicle(self, guild: Guild) -> Chronicle:
        if guild.id not in self.chronicles:
            # For now, chronicle channel names are hard-coded
            self.chronicles[guild.id] = Chronicle(guild, self.CHRONICLE_CHANNEL)
        return self.chronicles[guild.id]

    def get_all_plugins(self, guild: Guild) -> List[Plugin]:
        plugins = [
            BasePlugin(self, self.get_roleplay_for_guild(guild.id))
        ]
        plugins += State.get_plugins(guild.id)
        return plugins

    async def refresh_from_config(
            self, guild: Guild, config: Dict[str, Any], force_reset=False
    ):
        logging.info(f'Refreshing server state from config for {guild.name}')

        State.save_config(guild.id, config)
        if 'rp' not in config or not config['rp']:
            return

        modified_config = False
        roleplay = self.roleplays[config['rp']]
        if 'connections' not in config:
            config['connections'] = {}
            modified_config = True
        for connection in roleplay.connections:
            if connection.name not in config['connections']:
                config['connections'][connection.name] = {
                    'h': connection.hidden,
                    'l': connection.locked,
                    'k': []
                }
                modified_config = True
        if modified_config:
            State.save_config(guild.id, config)
            await self.save_guild_config(guild, config)

        # Pick all the plugins required by the roleplay
        plugins = []
        plugin_configs = roleplay.plugins
        if plugin_configs:
            for plugin_id, plugin_config \
                    in plugin_configs.items():
                # noinspection PyArgumentList
                plugins.append(
                    self.plugins[plugin_id](
                        self,
                        roleplay,
                        **plugin_config
                    )
                )
        State.save_plugins(guild.id, plugins)

        # Ensure the server state matches
        gm_role = await self.create_or_update_role(guild, roleplay.roles['gm'])
        player_role = await self.create_or_update_role(
            guild, roleplay.roles['player']
        )
        observer_role = await self.create_or_update_role(
            guild, roleplay.roles['observer']
        )
        State.save_roles(guild.id, gm_role, player_role, observer_role)

        sections: Dict[str, CategoryChannel] = {
            c.name: c for c in guild.categories
        }
        for channel_id, room in roleplay.rooms.items():
            source = guild
            if room.section:
                if room.section not in sections:
                    sections[room.section] = await guild.create_category(
                        room.section,
                    )
                section = sections[room.section]
                source = section
            channel: TextChannel = next(
                (c for c in source.text_channels if c.name == channel_id),
                None
            )
            overwrites = {
                guild.default_role: PermissionOverwrite(
                    read_messages=False
                ),
                self.user: PermissionOverwrite(read_messages=True),
                gm_role: PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                ),
                observer_role: PermissionOverwrite(
                    read_messages=True,
                    send_messages=False
                )
            }
            if channel:
                if not force_reset:
                    continue
                await channel.edit(topic=room.description)
                for target, overwrite in overwrites.items():
                    await channel.set_permissions(target, overwrite=overwrite)
            else:
                await source.create_text_channel(
                    channel_id, topic=room.description, overwrites=overwrites
                )

    async def save_guild_config(self, guild: Guild, config: Dict[str, Any]):
        for channel in guild.text_channels:
            if channel.name == self.BOT_CONFIG_CHANNEL:
                config_channel = channel
                break
        else:
            config_channel = await guild.create_text_channel(
                self.BOT_CONFIG_CHANNEL,
                overwrites={
                    guild.default_role: PermissionOverwrite(
                        read_messages=False
                    ),
                    self.user: PermissionOverwrite(read_messages=True)
                }
            )
        json_config = json.dumps(config, separators=(',', ':'))
        i = 0
        # last_message = config_channel.last_message
        # async for message in config_channel.history(before=last_message):
        #     await message.delete()
        # if last_message:
        #     await last_message.delete()
        while True:
            json_chunk = json_config[i*1990:(i+1)*1990]
            if not json_chunk:
                break
            await config_channel.send(
                f'```\n{"^" if i != 0 else ""}{json_chunk}```'
            )
            i += 1

    @staticmethod
    async def create_or_update_role(
            guild: Guild, role_spec: Role
    ) -> discord.Role:
        role: discord.Role = next(
            (r for r in guild.roles if r.name == role_spec.label),
            None
        )
        if not role:
            role = await guild.create_role(name=role_spec.label)
        try:
            await role.edit(
                color=Color(role_spec.color),
                hoist=True,
                mentionable=True
            )
        except Forbidden:
            logging.warning("Cannot edit role, skipping")
        return role

    def get_roleplay_for_guild(self, guild_id: int):
        config = State.get_config(guild_id)
        return self.roleplays[config['rp']] \
            if config and 'rp' in config and config['rp'] else None

    @staticmethod
    def load_plugins(plugins_dir: str) -> Dict[str, Type[Plugin]]:
        plugins = {}
        for plugin_file in glob(os.path.join(plugins_dir, '*.py')):
            plugin_name = os.path.splitext(os.path.basename(plugin_file))[0]
            plugin_spec = importlib.util.spec_from_file_location(
                plugin_name, plugin_file
            )
            plugin = importlib.util.module_from_spec(plugin_spec)
            # noinspection PyUnresolvedReferences
            plugin_spec.loader.exec_module(plugin)
            # noinspection PyUnresolvedReferences
            plugins[plugin_name] = plugin.PLUGIN
        return plugins

    @staticmethod
    def load_roleplays(roleplays_dir: str) -> Dict[str, Roleplay]:
        roleplays = {}
        yaml.add_constructor('!connection', Connection.load)
        yaml.add_constructor('!role', Role.load)
        yaml.add_constructor('!roleplay', Roleplay.load)
        yaml.add_constructor('!room', Room.load)
        for roleplay_file in glob(os.path.join(roleplays_dir, '*.yaml')):
            with open(roleplay_file) as f:
                roleplay = yaml.load(f, Loader=yaml.Loader)
                roleplays[roleplay.id] = roleplay
        return roleplays
