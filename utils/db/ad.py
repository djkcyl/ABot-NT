from datetime import datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from models.ad import AdvertisementCategory
from utils.datetime import CHINA_TZ


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
