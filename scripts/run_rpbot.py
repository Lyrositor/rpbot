import logging

import toml
from rpbot.bot import RoleplayBot

DEFAULT_CONFIG_FILE_NAME = 'config.toml'


def main():
    logging.basicConfig(
        format='[%(asctime)s] %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logging.info('Starting up roleplay bot')

    with open(DEFAULT_CONFIG_FILE_NAME) as f:
        config = toml.load(f)
    bot = RoleplayBot(
        config['rpbot']['plugins_dir'],
        config['rpbot']['roleplays_dir'],
        config['rpbot']['admins']
    )
    bot.run(config['rpbot']['token'])


if __name__ == '__main__':
    main()
