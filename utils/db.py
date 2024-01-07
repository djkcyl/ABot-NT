from datetime import datetime
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from models.ad import AdvertisementCategory
from models.tcm.ims import IMSResponseModel
from models.tcm.tms import TMSResponseModel
from utils.datetime import CHINA_TZ


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
    banned: bool = False
    join_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)

    class Settings:
        name = "core_user"
        indexes = [IndexModel("aid", unique=True), IndexModel("cid", unique=True)]

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

class SignLog(Document):
    qid: str
    group_id: str
    sign_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)

    class Settings:
        name = "core_log_sign"
        indexes = [IndexModel("qid")]


class CoinLog(Document):
    qid: str
    group_id: str | None
    coin: int
    source: str
    detail: str = ""
    time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)

    class Settings:
        name = "core_log_coin"
        indexes = [IndexModel("qid")]


class BanLog(Document):
    target_id: str
    target_type: Literal["user", "group"]
    action: Literal["ban", "unban"]
    ban_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)
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


class Advertisement(Document):
    ad_id: str
    content: str
    content_type: int
    ad_category: AdvertisementCategory
    source: str
    start_date: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)
    end_date: datetime
    weight: int = 1
    target_audience: list[str] = []
    is_active: bool = True
    bid_price: int = 0

    class Settings:
        name = "core_ad"
        indexes = [IndexModel("ad_id", unique=True), IndexModel("bid_price")]

    async def activate(self) -> None:
        self.is_active = True
        await self.save()  # type: ignore

    async def deactivate(self) -> None:
        self.is_active = False
        await self.save()  # type: ignore


class AdDisplayLog(Document):
    ad_id: str
    display_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)
    scene_id: str
    client_id: str
    target_audience: list[str]

    class Settings:
        name = "core_log_ad_display"
        indexes = [IndexModel("ad_id")]


class ImageContentReviewLog(Document):
    image_id: str
    review_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)
    result: IMSResponseModel

    class Settings:
        name = "core_log_content_review:image"
        indexes = [IndexModel("image_id")]


class TextContentReviewLog(Document):
    text_md5: str
    review_time: datetime
    result: TMSResponseModel

    class Settings:
        name = "core_log_content_review:text"
        indexes = [IndexModel("text_md5")]
