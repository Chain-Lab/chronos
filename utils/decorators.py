

# 装饰器，用于检验输入到base58部分函数的值是str或bytes类型
def scrub_base58_input(func):
    def wrapper(value):
        # isinstance: 判断是否是已知的某种类型
        if isinstance(value, str) and not isinstance(value, bytes):
            value = value.encode("ascii")

        if not isinstance(value, bytes):
            raise TypeError(
                "a bytes-like object is required (also str), not '%s'" %
                type(value).__name__)

        return func(value)

    return wrapper