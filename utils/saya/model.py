from dataclasses import dataclass
from enum import Enum
from typing import cast

from loguru import logger

from utils.db_model import AUser, BanLog, GroupData


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
    usage: list[str]
    options: list[dict[str, str]]
    example: list[dict[str, str]]
    can_be_disabled: bool
    default_enable: bool
    hidden: bool
    maintain: bool


class AUserModel(AUser):
    @classmethod
    async def init(cls, user: AUser | str | int):
        if isinstance(user, str | int):
            user_id = str(user)
        elif not isinstance(user, AUser):
            raise TypeError(f"无法识别的用户类型：{type(user)}")
        else:
            user_id = user.cid

        if isinstance(user, AUser):
            return user
        user_ = await AUser.find_one(AUser.cid == user_id)
        if user_ is None:
            last_userid = await AUser.find_one(sort=[("_id", -1)])
            uid = int(last_userid.uid) + 1 if last_userid else 1
            await AUser.insert(AUser(uid=uid, cid=user_id))
            user_ = await AUser.find_one(AUser.cid == user_id)
            logger.info(f"[Core.db] 已初始化用户：{user_id}")
            return cast(AUser, user_)
        return cast(AUser, user_)


class AGroupModel(GroupData):
    @classmethod
    async def init(cls, group: GroupData | str | int):
        if isinstance(group, str | int):
            group_id = str(group)
        elif not isinstance(group, GroupData):
            raise TypeError(f"无法识别的群组类型：{type(group)}")
        else:
            group_id = group.group_id

        if isinstance(group, GroupData):
            return group
        group_ = await GroupData.find_one(GroupData.group_id == group_id)
        if group is None:
            await cls.insert(GroupData(group_id=group_id))
            group_ = await GroupData.find_one(GroupData.group_id == group_id)
            logger.info(f"[Core.db] 已初始化群：{group_id}")

            return cast(GroupData, group_)
        return cast(GroupData, group_)

    async def ban(self, reason: str, source: str):
        if self.banned:
            return False
        self.banned = True
        await GroupData.save(self)
        await BanLog.insert(
            BanLog(
                target_id=self.group_id,
                target_type="group",
                action="ban",
                ban_reason=reason,
                ban_source=source,
            )
        )
        return True

    async def unban(self, reason: str, source: str):
        if not self.banned:
            return False
        self.banned = False
        await GroupData.save(self)
        await BanLog.insert(
            BanLog(
                target_id=self.group_id,
                target_type="group",
                action="unban",
                ban_reason=reason,
                ban_source=source,
            )
        )
        return True

    async def disable_function(self, function: str, meta: "FuncItem"):
        if function in self.disable_functions or not meta.can_be_disabled:
            return False
        self.disable_functions.append(function)
        await GroupData.save(self)
        return True

    async def enable_function(self, function: str, meta: "FuncItem"):
        if function not in self.disable_functions or meta.maintain:
            return False
        self.disable_functions.remove(function)
        await GroupData.save(self)
        return True
