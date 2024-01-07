from enum import Enum


class AdvertisementCategory(str, Enum):
    business = "商业"
    public_welfare = "公益"
    announcement = "公告"
    tips = "提示"
