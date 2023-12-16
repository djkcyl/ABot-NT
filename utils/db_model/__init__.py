from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from beanie import Document
from pymongo import IndexModel


class AUser(Document):
    uid: int
    cid: str
    coin: int = 10
    is_sign: bool = False
    is_chat: bool = False
    today_transferred: int = 0
    total_sign: int = 0
    totle_talk: int = 0
    continue_sign: int = 0
    banned: bool = False
    join_time: datetime = datetime.now(ZoneInfo("Asia/Shanghai"))

    class Settings:
        name = "core_user"
        indexes = [IndexModel("uid", unique=True), IndexModel("cid", unique=True)]

    async def sign(self, group_id: str | int):
        if self.is_sign:
            return False
        self.is_sign = True
        self.total_sign += 1
        self.continue_sign += 1
        await self.save()
        await SignLog.insert(SignLog(qid=self.cid, group_id=str(group_id)))
        return True

    async def ban(self, reason: str, source: str):
        if self.banned:
            return False
        self.banned = True
        await self.save()
        await BanLog.insert(
            BanLog(
                target_id=self.cid,
                target_type="user",
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
        await self.save()
        await BanLog.insert(
            BanLog(
                target_id=self.cid,
                target_type="user",
                action="unban",
                ban_reason=reason,
                ban_source=source,
            )
        )
        return True

    async def add_coin(
        self,
        num: int,
        group_id: str | int | None = None,
        source: str = "未知",
        detail: str = "",
    ):
        self.coin += num
        await self.save()
        await CoinLog.insert(
            CoinLog(
                qid=self.cid,
                group_id=str(group_id),
                coin=num,
                source=source,
                detail=detail,
            )
        )

    async def reduce_coin(
        self,
        num: int,
        force: bool = False,
        group_id: str | int | None = None,
        source: str = "未知",
        detail: str = "",
    ):
        if self.coin < num:
            if not force:
                return False
            now_coin = self.coin
            self.coin = 0
            await self.save()
            await CoinLog.insert(
                CoinLog(
                    qid=self.cid,
                    group_id=str(group_id),
                    coin=-now_coin,
                    source=source,
                    detail=detail,
                )
            )
            return now_coin
        else:
            self.coin -= num
            await self.save()
            await CoinLog.insert(
                CoinLog(
                    qid=self.cid,
                    group_id=str(group_id),
                    coin=-num,
                    source=source,
                    detail=detail,
                )
            )
            return True

    async def add_talk(self):
        self.totle_talk += 1
        self.is_chat = True
        await self.save()


class SignLog(Document):
    qid: str
    group_id: str
    sign_time: datetime = datetime.now(ZoneInfo("Asia/Shanghai"))

    class Settings:
        name = "core_log_sign"
        indexes = [IndexModel("qid")]


class CoinLog(Document):
    qid: str
    group_id: str | None
    coin: int
    source: str
    detail: str = ""
    time: datetime = datetime.now(ZoneInfo("Asia/Shanghai"))

    class Settings:
        name = "core_log_coin"
        indexes = [IndexModel("qid")]


class BanLog(Document):
    target_id: str
    target_type: Literal["user", "group"]
    action: Literal["ban", "unban"]
    ban_time: datetime = datetime.now(ZoneInfo("Asia/Shanghai"))
    ban_reason: str | None = None
    ban_source: str | None = None

    class Settings:
        name = "core_log_ban"


class GroupData(Document):
    group_id: str
    disable_functions: list[str] = []
    banned: bool = False

    class Settings:
        name = "core_group"
        indexes = [IndexModel("group_id", unique=True)]
