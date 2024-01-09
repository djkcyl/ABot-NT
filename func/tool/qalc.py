import asyncio

from avilla.core import Context, MessageReceived
from avilla.twilight.twilight import FullMatch, RegexResult, Twilight, WildcardMatch
from graia.saya import Channel
from graia.scheduler.saya.schema import SchedulerSchema
from graia.scheduler.timers import crontabify
from graiax.shortcut import dispatch, listen
from loguru import logger

from models.saya import FuncType
from utils.message.picture import SelfPicture
from utils.message.preprocessor import MentionMe
from utils.saya import build_metadata
from utils.text2image import md2img

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.tool,
    name="多功能计算器",
    version="1.0",
    description="一款多用途的计算器，支持单位换算和转换，货币换算，数学表达式计算，日期计算，方程求解等",
    cmd_prefix="qalc",
    usage=["发送指令：/qalc <expression>"],
    options=[{"name": "expression", "help": "要计算的表达式"}],
    example=[
        {"run": "/qalc 1+1", "to": "计算 1 加 1 的结果"},
        {"run": "/qalc 1usd to jpy", "to": "将 1 美元转换为相等的日元"},
        {"run": "/qalc 1m + 1km * 20cm", "to": "计算 1 米加上 1 千米乘以 20 厘米的总和"},
        {"run": "/qalc today - 5 day - 1 month", "to": "计算今天往前推 1 个月零 5 天的日期"},
        {"run": "/qalc solve2(5x=2y^2; sqrt(y)=2; x; y)", "to": "解方程组 5x=2y^2 和 sqrt(y)=2"},
        {"run": "/qalc 50 Ω * 2 A", "to": "计算 50 欧姆的电阻器在 2 安培电流下的电压"},
    ],
    maintain=True,
)


async def run_cli_command(command: list[str]) -> str | None:
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        output = stdout.decode().strip()
        logger.debug(f"Command: {command} Output: {output}")
        return output
    logger.error(f"Error executing command: {command}")
    logger.error(stderr.decode().strip())
    return None


@channel.use(SchedulerSchema(crontabify("0 * * * *")))
async def update_qalc():  # noqa: ANN201
    logger.info("[Task.qalc] Start update qalc exchange rate")
    result = await run_cli_command(["qalc", "-e", "1-1"])
    if result is None:
        logger.error(f"[Task.qalc] Update qalc exchange rate failed")
    else:
        logger.success("[Task.qalc] Update qalc exchange rate success")


@listen(MessageReceived)
@dispatch(Twilight([FullMatch("qalc"), "result" @ WildcardMatch()], preprocessor=MentionMe()))
async def main(ctx: Context, result: RegexResult):  # noqa: ANN201
    if result.result:
        command = ["qalc", str(result.result)]
        cli_result = await run_cli_command(command) or "无法获取结果"
        cli_result = "\n\n".join(cli_result.splitlines())
        await ctx.scene.send_message(
            await SelfPicture().from_data(
                await md2img(
                    f"### 输入：\n{result.result!s}\n### 结果:\n{cli_result}",
                )
            )
        )

    else:
        await ctx.scene.send_message("请发送正确的表达式，例如：/qalc 1+1")
