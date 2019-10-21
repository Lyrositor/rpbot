from typing import List

from yaml import YAMLObject

from rpbot.data.object import Object


class Room(YAMLObject):
    yaml_tag = '!room'

    def __init__(self, section: str, description: str, objects: List[Object]):
        self.section = section
        self.description = description
        self.objects = objects
