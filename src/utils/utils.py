import sys
import orjson
from typing import Any
from typing_extensions import Doc, get_type_hints


def get_func_name(depth: int = 1):
    """获取调用者的函数名
    
    获取上一级调用栈的函数名称。
    depth=2 则 为上上级 以此类推
    
    Returns:
        调用者的函数名字符串
    """
    return sys._getframe(depth).f_code.co_name


def to_json(obj):
    """将对象序列化为 JSON 字符串
    
    Args:
        obj: 任意可序列化对象
        
    Returns:
        JSON 格式的字符串
    """
    return orjson.dumps(obj).decode("utf-8")


def to_one_line(text: str):
    """将多行文本转为单行
    
    将换行符替换为转义字符，用于日志或单行输出。
    
    Args:
        text: 原始文本
        
    Returns:
        单行文本
    """
    return text.strip().replace("\n", "\\n")


def copy_data_by_model(model: dict, data: dict | list[dict]) -> dict | list[dict]:
    """根据 model 复制数据
    
    只复制 data 中存在的、且 model 类中定义的属性。
    用于从模型中提取有效字段。
    
    Args:
        model: 模型类
        data: 要复制的数据字典或列表
        
    Returns:
        复制后的数据字典或列表
    """
    new_data = []
    copy_data = data if isinstance(data, list) else [data]
    for item in copy_data:
        new_data.append({k: v for k, v in item.items() if k in model.__annotations__})
    return new_data if isinstance(data, list) else new_data[0]


def get_field_doc(cls: Any, field: str) -> str | None:
    """获取 Annotated[x,Doc(xxx)] 字段 Doc 中的注释
    
    从类型注解的 metadata 中提取 Doc 文档字符串。
    
    Args:
        cls: 类对象
        field: 字段名
        
    Returns:
        字段的 Doc 文档字符串，不存在返回 None
    """
    hints = get_type_hints(cls, include_extras=True)
    field_hint = hints.get(field)
    if field_hint is None:
        return None
    metadata = getattr(field_hint, "__metadata__", [])
    for item in metadata:
        if isinstance(item, Doc):
            return item.documentation
    return None
