from datetime import datetime
from typing import Literal

from avilla.core import MessageChain
from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from models.tcm.ims import IMSResponseModel
from models.tcm.tms import TMSResponseModel
from utils.datetime import CHINA_TZ


class ChatLog(Document):
    qid: str
    group_id: str | None
    message_id: str
    message_display: str
    time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)

    class Settings:
        name = "core_log_chat"
        indexes = [IndexModel("qid")]


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
