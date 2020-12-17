from rpbot.data.base import YAMLObjectWithDefaults


class Role(YAMLObjectWithDefaults):
    def __init__(self, label: str, color: str):
        self.label = label
        self.color = color
