from rpbot.data.base import YAMLObjectWithDefaults


class Connection(YAMLObjectWithDefaults):
    def __init__(
            self,
            room1: str,
            room2: str,
            timer: int = 0,
            hidden: bool = False,
            locked: bool = False,
    ):
        self.room1 = room1
        self.room2 = room2
        self.timer = timer
        self.hidden = hidden
        self.locked = locked

    @property
    def name(self):
        return f'{self.room1}#{self.room2}'
