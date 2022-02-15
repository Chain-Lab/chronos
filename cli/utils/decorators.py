

# 装饰器，用于检验输入到base58部分函数的值是str或bytes类型
def scrub_base58_input(func):
    """
    :param func: 用于装饰的函数，要求输入的数据为str或bytes
    :return: 经过函数处理后返回的数据
    """
    def wrapper(value):
        """
        :param value: 输入数据 (类型为str 或 bytes)
        :return: 编码/解码后的数据
        """
        # isinstance: 判断是否是已知的某种类型
        if isinstance(value, str) and not isinstance(value, bytes):
            value = value.encode("ascii")

        if not isinstance(value, bytes):
            raise TypeError(
                "a bytes-like object is required (also str), not '%s'" %
                type(value).__name__)

        return func(value)

    return wrapper
