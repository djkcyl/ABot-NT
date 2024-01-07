from dataclasses import dataclass
from enum import Enum


class FuncType(str, Enum):
    core = "核心"
    user = "用户"
    tool = "工具"
    fun = "娱乐"
    push = "推送"
    admin = "管理"


@dataclass
class FuncItem:
    func_type: FuncType
    name: str
    version: str
    description: str
    cmd_prefix: str
    usage: list[str]
    options: list[dict[str, str]]
    example: list[dict[str, str]]
    tips: list[str]
    can_be_disabled: bool
    default_enable: bool
    hidden: bool
    maintain: bool
