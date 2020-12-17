from yaml import YAMLObject


class YAMLObjectWithDefaults(YAMLObject):
    @classmethod
    def load(cls, loader, node):
        fields = loader.construct_mapping(node)
        # noinspection PyArgumentList
        return cls(**fields)
