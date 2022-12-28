class STATUS(object):
    """
    状态码的定义
    不使用Enum是因为不能直接json序列化
    """
    EMPTY_MSG = 0
    HANDSHAKE = 1
    PULL_BLOCK = 2
    PUSH_BLOCK = 3
    NEW_BLOCK = 4
    NEW_BLOCK_HASH = 5
    GET_BLOCK = 6
    BLOCK_KNOWN = 7
