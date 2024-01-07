import math
import random
from datetime import datetime, timedelta
from secrets import token_hex
from typing import TYPE_CHECKING, Literal, cast

from avilla.core import Context
from beanie import SortDirection
from beanie.odm.operators.find.comparison import GT, LTE, Eq, In
from loguru import logger

from models.ad import AdvertisementCategory
from utils.datetime import CHINA_TZ
from utils.db import AdDisplayLog, Advertisement, AUser, BanLog, GroupData

if TYPE_CHECKING:
    from models.saya import FuncItem


class ADBuilder(Advertisement):
    @classmethod
    async def create_ad(
        cls,
        content: str,
        content_type: int,
        category: AdvertisementCategory,
        source: str,
        expire_days: int = 30,
        weight: int = 1,
        target_audience: list[str] | None = None,
        bid_price: int = 0,
    ) -> str:
        if target_audience is None:
            target_audience = []
        while True:
            ad_id = token_hex(8)
            if await cls.find_one(cls.ad_id == ad_id):
                continue
            break

        await cls.insert(
            Advertisement(
                ad_id=ad_id,
                content=content,
                content_type=content_type,
                ad_category=category,
                source=source,
                end_date=datetime.now(CHINA_TZ) + timedelta(days=expire_days) if expire_days else datetime.max,
                weight=weight,
                target_audience=target_audience,
                bid_price=bid_price,
            )
        )
        return ad_id

    # 随机抽取广告
    @classmethod
    async def get_ad(
        cls, category: AdvertisementCategory | None = None, target_audience: list[str] | None = None
    ) -> Advertisement | None:
        if target_audience is None:
            target_audience = []
        current_date = datetime.now(CHINA_TZ)

        # 构建查询条件
        query = cls.find(
            Eq(cls.is_active, True),
            LTE(cls.start_date, current_date),
            GT(cls.end_date, current_date),
        )

        if category:
            query = query.find(Eq(cls.ad_category, category))

        if target_audience:
            query = query.find(In(cls.target_audience, target_audience))

        # 计算每个广告的调整后的权重
        ads = await query.to_list()

        if not ads:
            return None

        adjusted_weights = [math.log1p(ad.bid_price) * math.log1p(ad.weight) for ad in ads]
        total_weight = sum(adjusted_weights)

        # 根据权重随机选择广告
        probabilities = [w / total_weight for w in adjusted_weights]
        selected_ad = random.choices(ads, weights=probabilities, k=1)

        ctx = Context.current
        cid = ctx.client.last_value
        if ctx.scene.path_without_land in {"guild.channel", "guild.user"}:
            sid = ctx.scene["guild"]
        else:
            sid = ctx.scene["group"]

        selected_ad = selected_ad[0]
        selected_ad.views += 1
        await selected_ad.save()  # type: ignore
        selected_ad = cast(Advertisement, selected_ad)

        await AdDisplayLog.insert(
            AdDisplayLog(
                ad_id=selected_ad.ad_id,
                scene_id=sid,
                client_id=cid,
                target_audience=list(set(selected_ad.target_audience) & set(target_audience)),
            )
        )
        return selected_ad


class AGroupBuilder(GroupData):
    @classmethod
    async def init(cls, group: GroupData | str | int) -> GroupData:
        if isinstance(group, str | int):
            group_id = str(group)
        elif not isinstance(group, GroupData):
            msg = f"无法识别的群组类型: {type(group)}"
            raise TypeError(msg)
        else:
            group_id = group.group_id

        if isinstance(group, GroupData):
            return group
        group_ = await GroupData.find_one(Eq(GroupData.group_id, group_id))
        if group is None:
            await cls.insert(GroupData(group_id=group_id))
            group_ = await GroupData.find_one(Eq(GroupData.group_id, group_id))
            logger.info(f"[Core.db] 已初始化群: {group_id}")

            return cast(GroupData, group_)
        return cast(GroupData, group_)

    async def ban(self, reason: str, source: str) -> bool:
        if self.banned:
            return False
        self.banned = True
        await GroupData.save()  # type: ignore
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

    async def unban(self, reason: str, source: str) -> bool:
        if not self.banned:
            return False
        self.banned = False
        await GroupData.save()  # type: ignore
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

    async def disable_function(self, function: str, meta: "FuncItem") -> bool:
        if function in self.disable_functions or not meta.can_be_disabled:
            return False
        self.disable_functions.append(function)
        await GroupData.save()  # type: ignore
        return True

    async def enable_function(self, function: str, meta: "FuncItem") -> bool:
        if function not in self.disable_functions or meta.maintain:
            return False
        self.disable_functions.remove(function)
        await GroupData.save()  # type: ignore
        return True


class AUserBuilder(AUser):
    @classmethod
    async def get_user(cls, user: AUser | str | int, create_type: Literal["cid", "aid"] = "cid") -> AUser | None:
        if isinstance(user, str | int):
            if isinstance(user, str) and not user.isdigit():
                msg = f"无法识别的用户类型: {type(user)}"
                raise ValueError(msg)
            user_id = str(user)
        elif not isinstance(user, AUser):
            msg = f"无法识别的用户类型: {type(user)}"
            raise TypeError(msg)
        else:
            user_id = user.cid

        if isinstance(user, AUser):
            return user
        if create_type == "cid":
            user_: AUser | None = await AUser.find_one(Eq(AUser.cid, user_id))
        elif create_type == "aid":
            user_: AUser | None = await AUser.find_one(Eq(AUser.aid, int(user_id)))
        else:
            msg = f"无法识别的用户类型: {create_type}"
            raise TypeError(msg)
        return user_

    @classmethod
    async def init(cls, user: AUser | str | int, create_type: Literal["cid", "aid"] = "cid") -> AUser:
        if isinstance(user, str | int):
            if isinstance(user, str) and not user.isdigit():
                msg = f"无法识别的用户类型: {user}"
                raise ValueError(msg)
            user_id = str(user)
        elif not isinstance(user, AUser):
            msg = f"无法识别的用户类型: {type(user)}"
            raise TypeError(msg)
        else:
            user_id = user.cid

        if isinstance(user, AUser):
            return user
        if create_type == "cid":
            user_ = await AUser.find_one(Eq(AUser.cid, user_id))
        elif create_type == "aid":
            user_ = await AUser.find_one(Eq(AUser.aid, int(user_id)))
        else:
            msg = f"无法识别的用户类型: {create_type}"
            raise TypeError(msg)
        if user_ is None:
            last_userid = await AUser.find_one(sort=[("_id", SortDirection.DESCENDING)])
            aid = int(last_userid.aid) + 1 if last_userid else 1
            await AUser.insert(AUser(aid=aid, cid=user_id))
            user_ = await AUser.find_one(Eq(AUser.aid, aid))
            logger.info(f"[Core.db] 已初始化用户: {user_id}")
            return cast(AUser, user_)
        return cast(AUser, user_)
