import decimal
import random
from datetime import datetime
from enum import Enum, auto

from beanie import Document, SortDirection
from beanie.odm.operators.find.comparison import NE, Eq, In
from beanie.odm.queries.find import FindMany
from pydantic import Field
from pymongo import IndexModel

from utils.datetime import CHINA_TZ


class ReviewStatus(Enum):
    PENDING = auto()  # 待审核
    APPROVED = auto()  # 人工审核通过
    AI_APPROVED = auto()  # AI审核通过
    REJECTED = auto()  # 审核不通过


class DriftingBottle(Document):
    bottle_id: int
    aid: int
    group_id: str
    text: str | None
    images: list[str] | None
    anonymous: bool
    total_pickups: int = 0
    remaining_pickups: int = -1
    review_status: ReviewStatus = ReviewStatus.PENDING
    create_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)
    isdelete: bool = False

    class Settings:
        name = "plugin_drift_bottle:drifting_bottle"
        indexes = [IndexModel("bottle_id"), IndexModel("aid")]

    async def pickup(self) -> None:
        self.total_pickups += 1
        if self.remaining_pickups > 0:
            self.remaining_pickups -= 1
        await self.save()  # type: ignore

    async def delete(self) -> None:
        self.isdelete = True
        await self.save()  # type: ignore

    async def get_score(self) -> float | None:
        return await get_bottle_score(self.bottle_id)

    async def get_score_count(self) -> int:
        return await BottleScore.find(Eq(BottleScore.bottle_id, self.bottle_id)).count()

    async def get_discuss(self) -> list["BottleDiscuss"]:
        return await BottleDiscuss.find(Eq(BottleDiscuss.bottle_id, self.bottle_id)).to_list()

    async def get_discuss_count(self) -> int:
        return await BottleDiscuss.find(Eq(BottleDiscuss.bottle_id, self.bottle_id)).count()


class BottleScore(Document):
    bottle_id: int
    aid: int
    score: int
    create_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)

    class Settings:
        name = "plugin_drift_bottle:bottle_score"
        indexes = [IndexModel("bottle_id"), IndexModel("aid")]


class BottleDiscuss(Document):
    bottle_id: int
    aid: int
    text: str
    create_time: datetime = Field(default_factory=datetime.now, tzinfo=CHINA_TZ)

    class Settings:
        name = "plugin_drift_bottle:bottle_discuss"
        indexes = [IndexModel("bottle_id"), IndexModel("aid")]


async def throw_bottle(
    aid: int,
    group_id: str,
    text: str | None = None,
    remaining_pickups: int = -1,
    images: list[str] | None = None,
    review_status: ReviewStatus = ReviewStatus.PENDING,
    *,
    anonymous: bool = False,
) -> int:
    if not text and not images:
        msg = "漂流瓶内容不能为空!"
        raise ValueError(msg)

    last_id = await DriftingBottle.find_one(sort=[("_id", SortDirection.DESCENDING)])
    bottle_id = int(last_id.bottle_id) + 1 if last_id else 1

    await DriftingBottle.insert(
        DriftingBottle(
            bottle_id=bottle_id,
            aid=aid,
            text=text,
            images=images,
            remaining_pickups=remaining_pickups,
            group_id=group_id,
            anonymous=anonymous,
            review_status=review_status,
        )
    )
    bottle = await DriftingBottle.find_one(Eq(BottleScore.bottle_id, bottle_id))
    if not bottle:
        msg = "漂流瓶创建失败"
        raise ValueError(msg)
    return bottle.bottle_id


async def get_bottle_score(bottle_id: int) -> float | None:
    scores = BottleScore.find(Eq(BottleScore.bottle_id, bottle_id)).sort(("score", SortDirection.ASCENDING))
    score_count = await scores.count()
    if score_count < 3:
        return None
    scores = await scores.to_list()
    scores = scores[int(score_count * 0.05) : int(score_count * 0.95)]
    return round(sum(i.score for i in scores) / len(scores), 1)


async def get_random_bottle() -> DriftingBottle | None:
    bottles = DriftingBottle.find(
        NE(DriftingBottle.remaining_pickups, 0),
        Eq(DriftingBottle.isdelete, False),
        In(DriftingBottle.review_status, [ReviewStatus.APPROVED, ReviewStatus.AI_APPROVED]),
    )
    bottles = await bottles.aggregate([{"$sample": {"size": 3}}]).to_list()
    if not bottles:
        return None
    bottles = [DriftingBottle(**i) for i in bottles]
    weights = []
    for bottle in bottles:
        score = await get_bottle_score(bottle.bottle_id) or 3.0
        weight = int(decimal.Decimal(score).quantize(decimal.Decimal("1"), rounding=decimal.ROUND_HALF_UP))
        weights.append(weight)
    return random.choices(bottles, weights=weights)[0]


async def get_bottle_by_id(bottle_id: int) -> DriftingBottle | None:
    return await DriftingBottle.find_one(Eq(DriftingBottle.bottle_id, bottle_id))


def get_all_bottles() -> FindMany[DriftingBottle]:
    return DriftingBottle.find()


def get_bottles_by_aid(aid: int) -> FindMany[DriftingBottle]:
    return DriftingBottle.find_many(Eq(DriftingBottle.aid, aid), Eq(DriftingBottle.isdelete, False)).sort(
        ("_id", SortDirection.DESCENDING)
    )
