import math

from beanie.odm.enums import SortDirection
from graia.saya import Channel
from graia.scheduler.saya.schema import SchedulerSchema
from graia.scheduler.timers import crontabify
from loguru import logger

from utils.saya import build_metadata
from utils.saya.model import AUser, AUserModel, FuncType

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
async def main():
    all_num, sign_num, chat_num = await activity_count()
    # cache, delete_cache = delete_old_cache()
    total_rent = await ladder_rent_collection()

    task_text = (  # noqa: F841
        f"签到重置成功\n"
        f"签到率 {str(sign_num)} / {str(all_num)} "
        f"{f'{sign_num / all_num:.2%}' if all_num > 0 else 'NaN'}\n"
        f"活跃率 {str(chat_num)} / {str(all_num)} "
        f"{f'{chat_num / all_num:.2%}' if all_num > 0 else 'NaN'}\n"
        f"活跃签到率 {str(sign_num)} / {str(chat_num)} "
        f"{f'{sign_num / chat_num:.2%}' if chat_num > 0 else 'NaN'}\n"
        f"今日收取了 {total_rent} 游戏币\n"
        # f"缓存清理 {delete_cache}/{cache} 个"
    )
    [logger.info(f"[Task.daily] {line}") for line in task_text.split("\n") if line]

    await reset_status()


async def activity_count():
    all_num = await AUser.count()
    sign_num = await AUser.find_many(AUser.is_sign == True).count()
    chat_num = await AUser.find_many(AUser.is_chat == True).count()

    return all_num, sign_num, chat_num


async def ladder_rent_collection():
    user_list = AUser.find_many(AUser.coin >= 1000, sort=[("coin", SortDirection.DESCENDING)])
    total_rent = 0
    async for user in user_list:
        auser = await AUserModel.init(user)
        # leadder_rent 算法为超过 1000 的部分，每多 1000 个游戏币加收千分之一
        leadder_rent = math.ceil((user.coin - 1000) / 1000) / 1000
        reduce_coin = math.ceil(user.coin * leadder_rent)
        total_rent += reduce_coin
        await auser.reduce_coin(reduce_coin, source="梯度持有税", detail=f"税率：{leadder_rent}")
        logger.info(f"[Task.daily] {user.cid} 被收取了 {reduce_coin} 游戏币")
    return total_rent


async def reset_status():
    await AUser.find_many(AUser.is_sign == False).set({AUser.continue_sign: 0})
    await AUser.find_many(AUser.is_sign == True).set({AUser.is_sign: False})
    await AUser.find_many(AUser.is_chat == True).set({AUser.is_chat: False})
    await AUser.find_many(AUser.today_transferred > 0).set({AUser.today_transferred: 0})
    logger.info("[Task.daily] 用户日常状态重置成功")
