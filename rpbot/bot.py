import importlib.util
import json
import logging
import os
from glob import glob
from typing import List, Dict, Type, Any

import discord
import yaml

from rpbot.base_plugin import BasePlugin
from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin, PluginCommand
from rpbot.state import State


class RoleplayBot(discord.Client):
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
                        and isinstance(channel, discord.TextChannel) \
                        and channel.last_message_id is not None:
                    try:
                        config_message =\
                            await channel.fetch_message(channel.last_message_id)
                        config = json.loads(config_message.content[8:-3])
                        await self.refresh_from_config(guild.id, config)
                    except discord.NotFound:
                        logging.warning('No config message found, ignoring guild')
                    except json.JSONDecodeError:
                        logging.warning('Config is invalid, ignoring guild')
                    except:
                        logging.exception(
                            'Encountered unexpected error while setting up'
                        )
                    finally:
                        break

        logging.info('Setup complete')

    async def on_message(self, message: discord.Message):
        # Ignore all DMs
        if message.guild is None:
            return

        username = str(message.author)
        is_admin = username in self.admins

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
            await plugin.process_message(message, is_admin)

    async def refresh_from_config(self, guild_id: int, config: Dict[str, Any]):
        logging.info('Refreshing server state from config')

        State.save_config(guild_id, config)

        if 'rp' in config and config['rp']:
            roleplay = self.roleplays[config['rp']]
            plugin_configs = roleplay.plugins
            if plugin_configs:
                plugins = []
                for plugin_id, plugin_config \
                        in plugin_configs.items():
                    plugins.append(
                        self.plugins[plugin_id](
                            self,
                            roleplay,
                            **plugin_config
                        )
                    )
                State.save_plugins(guild_id, plugins)

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
