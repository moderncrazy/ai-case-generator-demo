from collections import Counter

from src.graphs.requirement.outline.schemas import RequirementModuleCreate


def validate_requirement_modules(modules: list[RequirementModuleCreate]) -> str:
    """
    验证需求模块列表的 name 和 order 是否合法。

    检查项：
    1. name 是否重复
    2. order 是否重复
    3. order 是否从 1 开始逐个递增

    Args:
        modules: 需求模块列表

    Returns:
        空字符串表示验证通过，错误信息字符串表示验证失败
    """
    errors = []
    names = [m.name for m in modules]
    orders = [m.order for m in modules]

    # 检查 name 重复
    name_counts = Counter(names)
    duplicate_names = [name for name, count in name_counts.items() if count > 1]
    if duplicate_names:
        errors.append(f"name 重复的模块：{', '.join(duplicate_names)}")

    # 检查 order 重复
    order_counts = Counter(orders)
    duplicate_orders = [str(order) for order, count in order_counts.items() if count > 1]
    if duplicate_orders:
        errors.append(f"order 重复的值：{', '.join(duplicate_orders)}")

    # 检查 order 是否从 1 开始逐个递增
    expected_orders = set(range(1, len(modules) + 1))
    actual_orders = set(orders)
    missing_orders = expected_orders - actual_orders
    if missing_orders:
        errors.append(f"order 序号不连续，缺失的序号：{', '.join(str(o) for o in sorted(missing_orders))}")
    return "，".join(errors)
