from avilla.core import Context, MessageReceived
from avilla.twilight.twilight import Twilight, UnionMatch
from graia.saya import Channel
from graiax.shortcut import dispatch, listen

from utils.message.picture import SelfPicture
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.saya.model import AUser, FuncType
from utils.text2image import md2img

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.user,
    name="个人数据",
    version="1.0",
    description="查看个人数据，例如签到天数等",
    can_be_disabled=False,
)


@listen(MessageReceived)
@dispatch(Twilight([UnionMatch("mydata", "我的数据", "查看个人信息")], preprocessor=MentionMe()))
async def main(ctx: Context, auser: AUser):
    await ctx.scene.send_message(
        await SelfPicture().from_data(
            await md2img(
                f"# 个人信息\n\n"
                f"AID：{auser.aid}\n"
                f"- 签到天数：{auser.total_sign}\n"
                f"- 签到连续天数：{auser.continue_sign}\n"
                f"- 游戏币：{auser.coin}\n"
                f"- 从有记录以来共 {auser.totle_talk} 次发言\n",
                width=300,
            )
        ),
    )
