import fire
from address import Address


class Pipeline(object):
    def __init__(self):
        self.address = Address()


if __name__ == "__main__":
    fire.Fire(Pipeline)
