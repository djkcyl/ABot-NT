from datetime import datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from utils.datetime import CHINA_TZ

from .log import BanLog, CoinLog, SignLog


class AUser(Document):
    aid: int
    cid: str
    coin: int = 10
    nickname: str | None = None
    is_sign: bool = False
    is_chat: bool = False
    today_transferred: int = 0
    total_sign: int = 0
    totle_talk: int = 0
    continue_sign: int = 0
    exp: int = 0
    banned: bool = False
    join_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)

    class Settings:
        name = "core_user"
        indexes = [IndexModel("aid", unique=True), IndexModel("cid", unique=True)]

    @property
    def level(self) -> int:
        """计算用户等级"""
        level_map = [0, 200, 1500, 4500, 10800, 28800, 74100, 190300, 488300]
        for i, v in enumerate(level_map):
            if self.exp < v:
                return i
        return len(level_map)

    @property
    def next_level_exp(self) -> int:
        """计算下一等级需要达到的经验"""
        level_map = [0, 200, 1500, 4500, 10800, 28800, 74100, 190300, 488300]
        for v in level_map:
            if self.exp < v:
                return v
        return 0

    @property
    def next_level_need(self) -> int:
        """计算距离升级下一等级还需要多少经验"""
        return self.next_level_exp - self.exp

    @property
    def exp_to_next_level(self) -> int:
        """计算当前等级升级到下一等级需要多少经验"""
        level_map = [0, 200, 1500, 4500, 10800, 28800, 74100, 190300, 488300]
        current_level = self.level
        if current_level >= len(level_map):
            return 0  # 当前等级已是最高等级，没有下一级
        return level_map[current_level] - level_map[current_level - 1]

    @property
    def progress_bar(self) -> str:
        """计算用户经验进度条"""
        total_length = 30
        # 计算当前等级起始的经验值
        current_level_start_exp = self.next_level_exp - self.exp_to_next_level

        # 从当前等级升级到下一等级所需的总经验
        exp_for_next_level = self.exp_to_next_level

        if exp_for_next_level == 0:
            # 当前等级已是最高等级，进度条为满
            return "[" + "#" * total_length + "] 100.0%"

        # 计算当前经验在当前等级的进度比例
        progress_ratio = (self.exp - current_level_start_exp) / exp_for_next_level
        progress_ratio = min(progress_ratio, 0.999)  # 确保进度条不会因为计算误差而显示为 100%
        progress_length = int(progress_ratio * total_length)
        progress_bar = "#" * progress_length
        remaining_bar = "-" * (total_length - progress_length)

        return f"[{progress_bar}{remaining_bar}] {progress_ratio * 100:.1f}%"

    async def sign(self, group_id: str | int) -> bool:
        if self.is_sign:
            return False
        self.is_sign = True
        self.total_sign += 1
        self.continue_sign += 1
        await self.save()  # type: ignore
        await SignLog.insert(SignLog(qid=self.cid, group_id=str(group_id)))
        return True

    async def ban(self, reason: str, source: str) -> bool:
        if self.banned:
            return False
        self.banned = True
        await self.save()  # type: ignore
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

    async def unban(self, reason: str, source: str) -> bool:
        if not self.banned:
            return False
        self.banned = False
        await self.save()  # type: ignore
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
    ) -> None:
        self.coin += num
        await self.save()  # type: ignore
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
        group_id: str | int | None = None,
        source: str = "未知",
        detail: str = "",
        *,
        force: bool = False,
    ) -> int | bool:
        if self.coin < num:
            if not force:
                return False
            now_coin = self.coin
            self.coin = 0
            await self.save()  # type: ignore
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
        self.coin -= num
        await self.save()  # type: ignore
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

    async def add_talk(self) -> None:
        self.totle_talk += 1
        self.is_chat = True
        await self.save()  # type: ignore

    async def set_nickname(self, nickname: str | None) -> None:
        self.nickname = nickname
        await self.save()  # type: ignore
