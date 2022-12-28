class STATUS(object):
    """
    状态码的定义
    不使用Enum是因为不能直接json序列化
    """
    HANDSHAKE = 0
    PULL_BLOCK = 1
    PUSH_BLOCK = 2
    NEW_BLOCK = 3
    NEW_BLOCK_HASH = 4
    GET_BLOCK = 5
    BLOCK_KNOWN = 6
