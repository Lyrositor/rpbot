from yaml import YAMLObject


class Connection(YAMLObject):
    yaml_tag = '!connection'

    def __init__(self, room1: str, room2: str, hidden: bool, locked: bool):
        self.room1 = room1
        self.room2 = room2
        self.hidden = hidden
        self.locked = locked

    @property
    def name(self):
        return f'{self.room1}#{self.room2}'
