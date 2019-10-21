from yaml import YAMLObject


class Object(YAMLObject):
    yaml_tag = '!object'

    def __init__(self, label: str, look: str, take: bool):
        self.label = label
        self.look = look
        self.take = take
