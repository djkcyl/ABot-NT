import math

from beanie.odm.enums import SortDirection
from beanie.odm.operators.find.comparison import GT, GTE, Eq
from beanie.odm.operators.update.general import Set
from graia.saya import Channel
from graia.scheduler.saya.schema import SchedulerSchema
from graia.scheduler.timers import crontabify
from loguru import logger

from models.saya import FuncType
from utils.builder import AUserBuilder
from utils.db import AUser
from utils.saya import build_metadata

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.core,
    name="日常维护",
    version="1.0",
    description="每日凌晨 4 点定时执行的任务",
    can_be_disabled=False,
    hidden=True,
)


@channel.use(SchedulerSchema(crontabify("0 4 * * *")))
async def main():  # noqa: ANN201
    all_num, sign_num, chat_num = await activity_count()
    # cache, delete_cache = delete_old_cache()
    total_rent = await ladder_rent_collection()

    task_text = (
        f"签到重置成功\n"
        f"签到率 {sign_num!s} / {all_num!s} "
        f"{f'{sign_num / all_num:.2%}' if all_num > 0 else 'NaN'}\n"
        f"活跃率 {chat_num!s} / {all_num!s} "
        f"{f'{chat_num / all_num:.2%}' if all_num > 0 else 'NaN'}\n"
        f"活跃签到率 {sign_num!s} / {chat_num!s} "
        f"{f'{sign_num / chat_num:.2%}' if chat_num > 0 else 'NaN'}\n"
        f"今日收取了 {total_rent} 游戏币\n"
        # f"缓存清理 {delete_cache}/{cache} 个"
    )
    [logger.info(f"[Task.daily] {line}") for line in task_text.split("\n") if line]

    await reset_status()


async def activity_count() -> tuple[int, int, int]:
    all_num = await AUser.count()
    sign_num = await AUser.find_many(Eq(AUser.is_sign, True)).count()
    chat_num = await AUser.find_many(Eq(AUser.is_chat, True)).count()

    return all_num, sign_num, chat_num


async def ladder_rent_collection() -> int:
    user_list = AUser.find_many(GTE(AUser.coin, 1000)).sort(("coin", SortDirection.DESCENDING))
    total_rent = 0
    async for user in user_list:
        auser = await AUserBuilder.init(user)
        # leadder_rent 算法为超过 1000 的部分，每多 100 个游戏币加收百分之一的税
        leadder_rent = math.ceil((user.coin - 1000) / 100) / 100
        reduce_coin = math.ceil(user.coin * leadder_rent)
        total_rent += reduce_coin
        await auser.reduce_coin(reduce_coin, source="梯度持有税", detail=f"税率：{leadder_rent}")
        logger.info(f"[Task.daily] {user.cid} 被收取了 {reduce_coin} 游戏币")
    return total_rent


async def reset_status() -> None:
    await AUser.find_many(Eq(AUser.is_sign, False)).update_many(Set({AUser.continue_sign: 0}))
    await AUser.find_many(Eq(AUser.is_sign, True)).update_many(Set({AUser.is_sign: False}))
    await AUser.find_many(Eq(AUser.is_chat, True)).update_many(Set({AUser.is_chat: False}))
    await AUser.find_many(GT(AUser.today_transferred, 0)).update_many(Set({AUser.today_transferred: 0}))
    logger.info("[Task.daily] 用户日常状态重置成功")
