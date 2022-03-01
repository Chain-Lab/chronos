import json
import logging

from jsonschema import validate
from jsonschema.exceptions import ValidationError


def json_validator(schema_file: str, data: dict):
    """
    校验传入的dict是否满足某个文件下的json规范
    :param schema_file: 存储规范的文件路径
    :param data: 需要进行校验的数据
    :return : 校验是否成功
    """

    with open(schema_file, "r") as f:
        schema = json.load(f)

    try:
        validate(instance=data, schema=schema)
    except ValidationError as err:
        logging.error("Json-Schema validate error.")
        return False

    return True
