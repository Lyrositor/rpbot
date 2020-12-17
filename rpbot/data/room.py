from rpbot.data.base import YAMLObjectWithDefaults


class Room(YAMLObjectWithDefaults):
    def __init__(self, section: str, description: str):
        self.section = section
        self.description = description
