from yaml import YAMLObject


class Role(YAMLObject):
    yaml_tag = '!role'

    def __init__(self, label: str, color: str):
        self.label = label
        self.color = color
