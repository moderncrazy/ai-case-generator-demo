import sys
import orjson


def get_func_name():
    return sys._getframe(1).f_code.co_name


def to_json(obj):
    return orjson.dumps(obj).decode("utf-8")


def to_one_line(text: str):
    return text.strip().replace("\n", "\\n")


def copy_data_by_model(model: dict, data: dict | list[dict]) -> dict | list[dict]:
    """根据 model 复制数据（只复制 model 中存在的属性）"""
    new_data = []
    copy_data = data if isinstance(data, list) else [data]
    for item in copy_data:
        new_data.append({k: v for k, v in item.items() if k in model.__annotations__})
    return new_data if isinstance(data, list) else new_data[0]
