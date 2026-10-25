"""统一的 UTC 时间工具。

项目所有 DateTime 列与既有数据均为 naive-UTC（无时区标记），MySQL DATETIME
不接受时区后缀，故这里刻意返回 naive 值——只换掉已弃用的 datetime.utcnow()
调用方式，不改变任何存储语义。
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """返回当前 UTC 时间（naive，与历史数据格式一致）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
