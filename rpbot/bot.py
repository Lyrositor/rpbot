import importlib.util
import json
import logging
import os
import sys
from glob import glob
from typing import List, Dict, Type, Any

import discord
import yaml
from discord import Client, CategoryChannel, TextChannel, PermissionOverwrite, \
    Guild, Message, NotFound, Color

from rpbot.base_plugin import BasePlugin
from rpbot.data.role import Role
from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommand
from rpbot.state import State


class RoleplayBot(Client):
    def __init__(
            self,
            plugins_dir: str,
            roleplays_dir: str,
            admins: List[str]
    ):
        super().__init__()

        self.admins = admins
        self.plugins = self._load_plugins(plugins_dir)
        self.roleplays = self._load_roleplays(roleplays_dir)

    def run(self, token: str):
        super().run(token)

    async def on_ready(self):
        for guild in self.guilds:
            for channel in guild.channels:
                if channel.name == BasePlugin.BOT_CONFIG_CHANNEL \
                        and isinstance(channel, TextChannel) \
                        and channel.last_message_id is not None:
                    # noinspection PyBroadException
                    try:
                        config_message =\
                            await channel.fetch_message(channel.last_message_id)
                        config = json.loads(config_message.content[8:-3])
                        await self.refresh_from_config(guild, config)
                    except NotFound:
                        logging.warning(
                            'No config message found, ignoring guild'
                        )
                    except json.JSONDecodeError:
                        logging.warning('Config is invalid, ignoring guild')
                    except:
                        logging.exception(
                            'Encountered unexpected error while setting up'
                        )
                        sys.exit(1)
                    finally:
                        break

        logging.info('Setup complete')

    async def on_message(self, message: Message):
        # Ignore all DMs
        if message.guild is None:
            return

        plugins = [
            BasePlugin(self,  self._get_roleplay_for_guild(message.guild.id))
        ]
        plugins += State.get_plugins(message.guild.id)

        # Do a special case for !help, since we need an overview of all plugins
        # to make it complete
        if message.clean_content == PluginCommand.PREFIX + 'help':
            help_message = '\n'.join(p.get_help() for p in plugins)
            if not help_message:
                help_message = 'No commands are currently available.'
            else:
                help_message = \
                    'The following commands are currently available:\n' \
                    + help_message
            await message.channel.send(help_message)
            return

        for plugin in plugins:
            await plugin.process_message(message)

    async def refresh_from_config(self, guild: Guild, config: Dict[str, Any]):
        logging.info('Refreshing server state from config')

        State.save_config(guild.id, config)
        if 'rp' not in config or not config['rp']:
            return

        roleplay = self.roleplays[config['rp']]

        # Pick all the plugins required by the roleplay
        plugins = []
        plugin_configs = roleplay.plugins
        if plugin_configs:
            for plugin_id, plugin_config \
                    in plugin_configs.items():
                plugins.append(
                    self.plugins[plugin_id](
                        self,
                        roleplay,
                        **plugin_config
                    )
                )
        State.save_plugins(guild.id, plugins)

        # Ensure the server state matches
        base_pos = guild.me.top_role.position
        gm_role = await self.create_or_update_role(
            guild, roleplay.roles['gm'], base_pos - 1
        )
        player_role = await self.create_or_update_role(
            guild, roleplay.roles['player'], base_pos - 2
        )
        observer_role = await self.create_or_update_role(
            guild, roleplay.roles['observer'], base_pos - 3
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
                        room.section
                    )
                section = sections[room.section]
                source = section
            channel: TextChannel = next(
                (c for c in source.text_channels if c.name == channel_id),
                None
            )
            if not channel:
                channel = await source.create_text_channel(channel_id)
            await channel.edit(topic=room.description)
            await channel.set_permissions(
                guild.default_role,
                read_messages=False,
                read_message_history=False
            )
            await channel.set_permissions(
                gm_role,
                read_messages=True,
                send_messages=True,
                read_message_history=True
            )
            await channel.set_permissions(
                observer_role,
                read_messages=True,
                send_messages=False,
                read_message_history=True
            )

    @staticmethod
    async def create_or_update_role(
            guild: Guild,
            role_spec: Role,
            position: int
    ) -> discord.Role:
        role: discord.Role = next(
            (r for r in guild.roles if r.name == role_spec.label),
            None
        )
        if not role:
            role = await guild.create_role(name=role_spec.label)
        await role.edit(
            color=Color(role_spec.color),
            hoist=True,
            mentionable=True,
            position=position
        )
        return role

    def _get_roleplay_for_guild(self, guild_id: int):
        config = State.get_config(guild_id)
        return self.roleplays[config['rp']] \
            if config and 'rp' in config and config['rp'] else None

    @staticmethod
    def _load_plugins(plugins_dir: str) -> Dict[str, Type[Plugin]]:
        plugins = {}
        for plugin_file in glob(os.path.join(plugins_dir, '*.py')):
            plugin_name = os.path.splitext(os.path.basename(plugin_file))[0]
            plugin_spec = importlib.util.spec_from_file_location(
                plugin_name, plugin_file
            )
            plugin = importlib.util.module_from_spec(plugin_spec)
            plugin_spec.loader.exec_module(plugin)
            plugins[plugin_name] = plugin.PLUGIN
        return plugins

    @staticmethod
    def _load_roleplays(roleplays_dir: str) -> Dict[str, Roleplay]:
        roleplays = {}
        for roleplay_file in glob(os.path.join(roleplays_dir, '*.yaml')):
            with open(roleplay_file) as f:
                roleplay = yaml.load(f, Loader=yaml.Loader)
                roleplays[roleplay.id] = roleplay
        return roleplays