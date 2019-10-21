from typing import TYPE_CHECKING

from rpbot.data.roleplay import Roleplay
from rpbot.plugin import Plugin

if TYPE_CHECKING:
    from rpbot.bot import RoleplayBot


class DemoPlugin(Plugin):
    def __init__(self, bot: 'RoleplayBot', roleplay: Roleplay, jolliness=1):
        super().__init__(bot, roleplay)
        self.jolliness = jolliness


PLUGIN = DemoPlugin
