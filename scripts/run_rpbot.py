import asyncio
import logging
import signal
from operator import itemgetter
from typing import Any, Dict

import aiohttp_jinja2
import jinja2
import toml
from aiohttp import web
# noinspection PyProtectedMember
from aiohttp.web import _run_app
from aiohttp.web_app import Application
from aiohttp.web_request import Request
from aiohttp.web_routedef import RouteTableDef
from aiohttp.web_runner import GracefulExit

from rpbot.bot import RoleplayBot
from rpbot.state import State

DEFAULT_CONFIG_FILE_NAME = 'config.toml'
STATIC_PATH = 'static'
TEMPLATES_PATH = 'templates'

routes = RouteTableDef()


async def global_variables(request: Request):
    bot: RoleplayBot = request.app['bot']
    roleplays = []
    for guild in bot.guilds:
        if bot.get_roleplay_for_guild(guild.id):
            roleplays.append({'id': guild.id, 'name': guild.name})

    try:
        guild_id = int(request.match_info['guild_id'])
    except (KeyError, ValueError):
        guild_id = None
    roleplay = None
    if guild_id is not None:
        config = State.get_config(guild_id)
        roleplay_data = bot.get_roleplay_for_guild(guild_id)
        if roleplay_data:
            guild = bot.get_guild(guild_id)
            roleplay = {
                'id': guild_id,
                'name': guild.name,
                'description': roleplay_data.description,
                'characters': [
                    {
                        'user_id': user_id,
                        'id': character_id,
                        **character,
                    }
                    for user_id, user_characters in config.get('characters', {}).items()
                    for character_id, character in user_characters['characters'].items()
                ],
                'commands': [
                    command for plugin in bot.get_all_plugins(guild)
                    for command in sorted(plugin.commands.values(), key=lambda c: c.name)
                    if command.enabled and not command.requires_admin
                ]
            }
    return {
        'roleplay': roleplay,
        'roleplays': sorted(roleplays, key=itemgetter('name')),
    }


@routes.get('/')
@aiohttp_jinja2.template('index.html')
async def home(request: Request):
    return {}


@routes.get(r'/{guild_id:\d+}')
@aiohttp_jinja2.template('index.html')
async def home_roleplay(request: Request):
    return {}


@routes.get(r'/{guild_id:\d+}/commands')
@aiohttp_jinja2.template('commands.html')
async def commands(request: Request):
    return {}


@routes.get(r'/{guild_id:\d+}/character/{user_id:\d+}/{character_id}')
@aiohttp_jinja2.template('character.html')
async def character(request: Request):
    try:
        guild_id = int(request.match_info['guild_id'])
    except (KeyError, ValueError):
        guild_id = None
    char = None
    if guild_id is not None:
        user_id = request.match_info['user_id']
        character_id = request.match_info['character_id']
        config = State.get_config(guild_id)
        characters_data = config.get('characters', {})
        char = characters_data.get(user_id, {}).get('characters', {}).get(character_id)
    return {
        'character': char
    }


async def run_bot(bot: RoleplayBot, config: Dict[str, Any]):
    try:
        await bot.start(config['rpbot']['token'])
    finally:
        if not bot.is_closed():
            await bot.close()


def run_website(bot: RoleplayBot):
    app = Application()
    app['bot'] = bot
    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
        context_processors=[global_variables]
    )
    app.add_routes(routes)
    app.add_routes([web.static('/', STATIC_PATH)])
    return _run_app(app, host='0.0.0.0', port=8081)


def run_bot_and_website():
    # Configure logging
    logging.basicConfig(
        format='[%(asctime)s] %(levelname)s - %(message)s',
        level=logging.INFO
    )

    # Configure the async loop to shut down cleanly when interrupted
    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
    except NotImplementedError:
        pass

    # Load config from file
    with open(DEFAULT_CONFIG_FILE_NAME) as f:
        config = toml.load(f)

    # Set up the bot
    bot = RoleplayBot(
        config['rpbot']['plugins_dir'],
        config['rpbot']['roleplays_dir'],
        config['rpbot']['admins']
    )

    logging.info('Starting up roleplay bot')
    asyncio.ensure_future(run_bot(bot, config), loop=loop)
    asyncio.ensure_future(run_website(bot), loop=loop)
    try:
        loop.run_forever()
    except (GracefulExit, KeyboardInterrupt):  # pragma: no cover
        logging.info('Shutting down roleplay bot')
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == '__main__':
    run_bot_and_website()
