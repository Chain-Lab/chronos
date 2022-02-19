import json


class STATUS(object):
    NODE_MSG = 0
    HAND_SHAKE_MSG = 1
    GET_BLOCK_MSG = 2
    TRANSACTION_MSG = 3
    POT = 4
    SYNC_MSG = 5
    UPDATE_MSG = 6


if __name__ == "__main__":
    print(json.dumps(STATUS.POT))

