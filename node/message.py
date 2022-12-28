from node.constants import STATUS


class Message(object):
    def __init__(self, code: STATUS, data):
        self.code = code
        self.data = data

    @classmethod
    def empty_message(cls):
        return cls(STATUS.EMPTY_MSG, "0")
