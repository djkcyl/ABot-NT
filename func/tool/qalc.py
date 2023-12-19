import asyncio
import sys

from avilla.core import Context, MessageReceived
from avilla.twilight.twilight import FullMatch, RegexResult, Twilight, WildcardMatch
from graia.saya import Channel
from graiax.shortcut import dispatch, listen

from utils.message.picture import SelfPicture
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.saya.model import FuncType
from utils.text2image import md2img

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.tool,
    name="多功能计算器",
    version="1.0",
    description="一款多用途的计算器，支持单位换算和转换，货币换算，数学表达式计算，日期计算，方程求解等",
    usage=["发送指令：/qacl <expression>"],
    options=[{"name": "expression", "help": "要计算的表达式"}],
    example=[
        {"run": "/qalc 1+1", "to": "计算 1 加 1 的结果"},
        {"run": "/qalc 1usd to jpy", "to": "将 1 美元转换为相等的日元"},
        {"run": "/qalc 1m + 1km * 20cm", "to": "计算 1 米加上 1 千米乘以 20 厘米的总和"},
        {"run": "/qalc today − 5 day - 1 month", "to": "计算今天往前推 1 个月零 5 天的日期"},
        {"run": "/qalc solve2(5x=2y^2; sqrt(y)=2; x; y)", "to": "解方程组 5x=2y^2 和 sqrt(y)=2"},
        {"run": "/qalc 50 Ω × 2 A", "to": "计算 50 欧姆的电阻器在 2 安培电流下的电压"},
    ],
)


async def run_cli_command(command):
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        return stdout.decode().strip()
    else:
        # 打印错误信息到标准错误
        print(f"Error executing command: {command}", file=sys.stderr)
        print(stderr.decode().strip(), file=sys.stderr)
        return None


@listen(MessageReceived)
@dispatch(Twilight([FullMatch("qalc"), "result" @ WildcardMatch()], preprocessor=MentionMe()))
async def main(ctx: Context, result: RegexResult):
    if result.result:
        command = ["qalc", str(result.result)]
        cli_result = await run_cli_command(command) or "无法获取结果"
        await ctx.scene.send_message(
            await SelfPicture().from_data(
                await md2img(f"### 输入：\n{str(result.result)}\n" f"### 结果:\n{cli_result}", 500)
            )
        )

    else:
        await ctx.scene.send_message("请发送正确的表达式，例如：/qalc 1+1")
