class STATUS(object):
    """
    状态码的定义
    不使用Enum是因为不能直接json序列化
    """
    NODE_MSG = 0
    HAND_SHAKE_MSG = 1
    GET_BLOCK_MSG = 2
    POT = 3
    SYNC_MSG = 4
    UPDATE_MSG = 5
    BLOCK = 6
