import random
from datetime import datetime
from zoneinfo import ZoneInfo

from avilla.core import Context, MessageReceived
from avilla.twilight.twilight import FullMatch, Twilight
from graia.saya import Channel
from graiax.shortcut import dispatch, listen

from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.saya.model import AUser, FuncType, GroupData

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.user,
    name="签到",
    version="1.0",
    description="用户签到，游戏币唯一的凭空来源",
    usage=["发送指令：签到"],
)


@listen(MessageReceived)
@dispatch(Twilight(FullMatch("/签到"), preprocessor=MentionMe()))
async def main(ctx: Context, auser: AUser, group: GroupData):
    if await auser.sign(group.group_id):
        if auser.continue_sign % 30 == 0:
            continue_reward = random.randint(0, 60)
            continue_twxt = f"获得 {continue_reward} 游戏币"
        elif auser.continue_sign % 7 == 0:
            continue_reward = random.randint(0, 15)
            continue_twxt = f"获得 {continue_reward} 游戏币"
        else:
            continue_reward = 0
            frist_sign = "首次签到，赠送 60 游戏币，" if auser.total_sign == 1 else ""
            remaining_days = min(30 - auser.continue_sign % 30, 7 - auser.continue_sign % 7)
            continue_twxt = f"{frist_sign}继续签到 {remaining_days} 天可获得额外奖励"

        frist_sign_gold = 60 if auser.total_sign == 1 else 0
        gold_add = (
            (random.randint(9, 21) if random.randint(1, 10) == 1 else random.randint(5, 12))
            + continue_reward
            + frist_sign_gold
        )
        await auser.add_coin(gold_add, group.group_id, "签到")
        sign_text = f"签到成功，本次共获得 {gold_add} 游戏币，你已连续签到 {auser.continue_sign} 天，{continue_twxt}"
    else:
        is_sign = "4 点之后再来吧" if datetime.now(ZoneInfo("Asia/Shanghai")).hour < 4 else "明天再来吧"
        sign_text = f"今天已经签过到了，{is_sign}"

    await ctx.scene.send_message(f"{time_nick()}，{sign_text}")


def time_nick():
    now_localtime = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
    if "06:00:00" < now_localtime < "08:59:59":
        return "早上好"
    elif "09:00:00" < now_localtime < "11:59:59":
        return "上午好"
    elif "12:00:00" < now_localtime < "13:59:59":
        return "中午好"
    elif "14:00:00" < now_localtime < "17:59:59":
        return "下午好"
    elif "18:00:00" < now_localtime < "23:59:59":
        return "晚上好"
    else:
        return "唔。。还没睡吗？早睡早起身体好喔！晚安❤"
