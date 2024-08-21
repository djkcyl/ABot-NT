import asyncio
import random
import re

from avilla.core import Context, MessageReceived
from avilla.twilight.twilight import (
    ArgResult,
    ArgumentMatch,
    FullMatch,
    ParamMatch,
    RegexResult,
    Twilight,
    UnionMatch,
)
from graia.broadcast.interrupt.waiter import Waiter
from graia.saya import Channel
from graia.saya.builtins.broadcast.schema import ListenerSchema
from graiax.shortcut import FunctionWaiter, dispatch, listen
from loguru import logger

from models.saya import FuncType
from utils.saya import build_metadata

from .game import draw_game, run_game, throw_prop
from .gamedata import HorseStatus, props

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.fun,
    name="赛马",
    version="1.0",
    description="有点刷屏的赛马小游戏",
    usage=[
        "发送指令：查看赛马信息",
        "发送指令：赛马抽奖",
        "发送指令：开始赛马 [-p, --prop]",
    ],
    options=[
        {"name": "查看赛马信息", "help": "查看自己的赛马信息"},
        {"name": "赛马抽奖", "help": "抽取一个道具"},
        {"name": "开始赛马", "help": "开始赛马小游戏"},
        {"name": "-p, --prop", "help": "开启道具模式"},
    ],
)

MEMBER_RUNING_LIST = []
GROUP_RUNING_LIST = []
GROUP_GAME_PROCESS = {}


@listen(MessageReceived)
@dispatch(Twilight([UnionMatch("bottle", "漂流瓶")], preprocessor=MentionMe()))
@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight([FullMatch("赛马")])],
        decorators=[
            Function.require("HorseRacing"),
            Permission.require(),
            Interval.require(),
        ],
    )
)
async def horse_racing(group: Group):
    await safeSendGroupMessage(
        group, MessageChain("赛马小游戏！\n发送“开始赛马”加入游戏\n发送“退出赛马”可以退出已加入的游戏或解散房间")
    )


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight([FullMatch("查看赛马信息")])],
        decorators=[
            Function.require("HorseRacing"),
            Permission.require(),
            Interval.require(),
        ],
    )
)
async def check_info(group: Group, member: Member):
    props = "\n".join([f"{amount} 个 {prop}" for prop, amount in get_props(member.id).items()]) or "无"
    await safeSendGroupMessage(
        group,
        MessageChain(At(member.id), Plain(f" 你共获胜 {get_wins(member.id)} 次\n你拥有的道具：\n{props}")),
    )


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight([FullMatch("赛马抽奖")])],
        decorators=[
            Function.require("HorseRacing"),
            Permission.require(),
            Interval.require(),
        ],
    )
)
async def lottery(group: Group, member: Member):
    prop_amount = get_props(member.id)
    i = sum(amount for _, amount in prop_amount.items() if amount)
    if i >= 10:
        await safeSendGroupMessage(group, MessageChain(At(member.id), Plain(" 你的背包已经满啦，请使用后再抽取吧！")))
    elif await reduce_gold(member.id, 2):
        prop = get_random_prop()
        add_prop(str(member.id), prop)
        await safeSendGroupMessage(group, MessageChain(At(member.id), Plain(f" 你获得了一个 {prop}")))
    else:
        await safeSendGroupMessage(group, MessageChain(At(member.id), f" 你的{COIN_NAME}不足，无法抽奖"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[
            Twilight(
                [
                    FullMatch("开始赛马"),
                    "plugin" @ ArgumentMatch("-p", "--prop", action="store_true", default=False),
                ]
            )
        ],
        decorators=[
            Function.require("HorseRacing"),
            Permission.require(),
            Interval.require(30),
        ],
    )
)
async def main(app: Ariadne, group: Group, member: Member, plugin: ArgResult):
    @Waiter.create_using_function(listening_events=[GroupMessage], using_decorators=[Permission.require()])
    async def waiter1(waiter1_group: Group, waiter1_member: Member, waiter1_message: MessageChain):
        if waiter1_group.id != group.id:
            return
        if waiter1_message.display == "加入赛马":
            player_list = GROUP_GAME_PROCESS[group.id]["members"]
            player_count = len(player_list)
            if player_count <= 8:
                if waiter1_member.id in GROUP_GAME_PROCESS[group.id]["members"]:
                    await safeSendGroupMessage(group, MessageChain("你已经参与了本轮游戏，请不要重复加入"))
                elif await reduce_gold(waiter1_member.id, 5):
                    GROUP_GAME_PROCESS[group.id]["members"].append(waiter1_member.id)
                    player_list = GROUP_GAME_PROCESS[group.id]["members"]
                    player_count = len(player_list)
                    if 8 > player_count > 1:
                        GROUP_GAME_PROCESS[group.id]["status"] = "pre_start"
                        add_msg = "，发起者可发送“提前开始”来强制开始本场游戏"
                    else:
                        GROUP_GAME_PROCESS[group.id]["status"] = "waiting"
                        add_msg = ""
                    await safeSendGroupMessage(
                        group,
                        MessageChain(
                            At(waiter1_member.id),
                            Plain(f" 你已成功加入本轮游戏，当前共有 {player_count} / 8 人参与{add_msg}"),
                        ),
                    )
                    if player_count >= 8:
                        GROUP_GAME_PROCESS[group.id]["status"] = "running"
                        return True
                else:
                    await safeSendGroupMessage(group, MessageChain(f"你的{COIN_NAME}不足，无法参加游戏"))
        elif waiter1_message.display == "退出赛马":
            player_list = GROUP_GAME_PROCESS[group.id]["members"]
            player_count = len(player_list)
            if waiter1_member.id == member.id:
                for player in GROUP_GAME_PROCESS[group.id]["members"]:
                    await add_gold(player, 5)
                MEMBER_RUNING_LIST.remove(member.id)
                GROUP_RUNING_LIST.remove(group.id)
                del GROUP_GAME_PROCESS[group.id]
                await safeSendGroupMessage(group, MessageChain("由于您是房主，本场房间已解散"))
                return False
            if waiter1_member.id in GROUP_GAME_PROCESS[group.id]["members"]:
                GROUP_GAME_PROCESS[group.id]["members"].remove(waiter1_member.id)
                player_list = GROUP_GAME_PROCESS[group.id]["members"]
                player_count = len(player_list)
                if 8 > player_count > 1:
                    GROUP_GAME_PROCESS[group.id]["status"] = "pre_start"
                else:
                    GROUP_GAME_PROCESS[group.id]["status"] = "waiting"
                await safeSendGroupMessage(
                    group,
                    MessageChain(
                        At(waiter1_member.id),
                        Plain(f" 你已退出本轮游戏，当前共有 {player_count} / 8 人参与"),
                    ),
                )
            else:
                await safeSendGroupMessage(group, MessageChain("你未参与本场游戏，无法退出"))
        elif waiter1_message.display == "提前开始":
            if waiter1_member.id == member.id:
                if GROUP_GAME_PROCESS[group.id]["status"] == "pre_start":
                    await safeSendGroupMessage(
                        group,
                        MessageChain(
                            At(waiter1_member.id),
                            Plain(" 已强制开始本场游戏"),
                        ),
                    )
                    GROUP_GAME_PROCESS[group.id]["status"] = "running"
                    return True
                await safeSendGroupMessage(
                    group,
                    MessageChain(
                        At(waiter1_member.id),
                        Plain(" 当前游戏人数不足，无法强制开始"),
                    ),
                )
            else:
                await safeSendGroupMessage(
                    group,
                    MessageChain(
                        At(waiter1_member.id),
                        Plain(" 你不是本轮游戏的发起者，无法强制开始本场游戏"),
                    ),
                )

    @Waiter.create_using_function(listening_events=[GroupMessage], using_decorators=[Permission.require()])
    async def waiter2(waiter2_group: Group, waiter2_member: Member, waiter2_message: MessageChain):
        if not plugin.result:
            return
        if waiter2_group.id != group.id or waiter2_member.id not in GROUP_GAME_PROCESS[group.id]["members"]:
            return
        props_list = list(props.keys())
        pattern = re.compile(f"(丢|使用)({'|'.join(props_list)})")
        if result := pattern.search(waiter2_message.display):
            prop = result[2]
            if use_prop(waiter2_member.id, result[2]):
                effect, value, duration, _ = props[prop]
                if effect == HorseStatus.Death:
                    status_result = "马匹遇害！"
                elif effect == HorseStatus.Poisoning:
                    status_result = f"马匹获得中毒效果！将在 {duration} 回合后死亡"
                elif effect == HorseStatus.Shield:
                    status_result = f"马匹获得了 {duration} 回合护盾"
                else:
                    status_result = f"马匹获得了 {value} 倍率的 {effect} 状态，将持续 {duration} 回合"
                if result[1] == "丢":
                    traget = random.choice(list(GROUP_GAME_PROCESS[group.id]["data"]["player"].keys()))
                    if GROUP_GAME_PROCESS[group.id]["data"]["player"][traget]["status"]["effect"] == HorseStatus.Shield:
                        await safeSendGroupMessage(
                            group,
                            MessageChain(
                                At(waiter2_member.id),
                                Plain(" 你对 "),
                                At(traget),
                                Plain(f" 使用了 {prop}，但是该马匹获得了护盾，无法生效"),
                            ),
                        )
                        return
                    elif (
                        GROUP_GAME_PROCESS[group.id]["data"]["player"][traget]["status"]["effect"] == HorseStatus.Death
                    ):
                        await safeSendGroupMessage(group, MessageChain("马匹已经死亡，无法使用道具"))
                    else:
                        await safeSendGroupMessage(
                            group,
                            MessageChain(
                                At(waiter2_member.id),
                                " 对 ",
                                "自己" if traget == waiter2_member.id else At(traget),
                                f" 丢出了{result[2]}，目标{status_result}",
                            ),
                        )

                elif result[1] == "使用":
                    traget = waiter2_member.id
                    if GROUP_GAME_PROCESS[group.id]["data"]["player"][traget]["status"]["effect"] == HorseStatus.Death:
                        await safeSendGroupMessage(group, MessageChain("马匹已经死亡，无法使用道具"))
                        return
                    else:
                        await safeSendGroupMessage(
                            group,
                            MessageChain(
                                At(waiter2_member.id),
                                f" 对自己使用了{result[2]}，{status_result}",
                            ),
                        )

                throw_prop(GROUP_GAME_PROCESS[group.id]["data"], traget, prop)
            else:
                await safeSendGroupMessage(group, MessageChain("你没有这个道具"))

    if group.id in GROUP_RUNING_LIST:
        if GROUP_GAME_PROCESS[group.id]["status"] == "running":
            return await safeSendGroupMessage(
                group,
                MessageChain(
                    At(member.id),
                    " 本轮游戏已经开始，请等待其他人结束后再开始新的一局",
                ),
            )
        elif GROUP_GAME_PROCESS[group.id]["status"] == "waiting" or "pre_start":
            return await safeSendGroupMessage(
                group,
                MessageChain(At(member.id), " 本群有一个正在等待的游戏，可发送“加入赛马”来加入该场游戏"),
            )
        else:
            return await safeSendGroupMessage(
                group, MessageChain(At(member.id), " 本群的游戏还未开始，请输入“加入赛马”参与游戏")
            )
    elif member.id in MEMBER_RUNING_LIST:
        return await safeSendGroupMessage(group, MessageChain(" 你已经参与了其他群的游戏，请等待游戏结束"))

    if await reduce_gold(member.id, 5):
        MEMBER_RUNING_LIST.append(member.id)
        GROUP_RUNING_LIST.append(group.id)
        GROUP_GAME_PROCESS[group.id] = {
            "status": "waiting",
            "members": [member.id],
            "data": None,
            "last_message": None,
        }
        await safeSendGroupMessage(
            group,
            MessageChain(
                "赛马小游戏开启成功，正在等待其他群成员加入，发送“加入赛马”参与游戏",
                "，本次游戏将开启道具模式" if plugin.result else "",
            ),
        )
    else:
        return await safeSendGroupMessage(group, MessageChain(f"你的{COIN_NAME}不足，无法开始游戏"))

    try:
        result = await asyncio.wait_for(inc.wait(waiter1), timeout=120)
        if result:
            GROUP_GAME_PROCESS[group.id]["status"] = "running"
            await safeSendGroupMessage(group, MessageChain("人数已满足，游戏开始！"))
        else:
            return

    except asyncio.TimeoutError:
        for player in GROUP_GAME_PROCESS[group.id]["members"]:
            await add_gold(player, 5)
        MEMBER_RUNING_LIST.remove(member.id)
        GROUP_RUNING_LIST.remove(group.id)
        del GROUP_GAME_PROCESS[group.id]
        return await safeSendGroupMessage(group, MessageChain("等待玩家加入超时，请重新开始"))

    await asyncio.sleep(3)
    # 开始游戏
    player_list = GROUP_GAME_PROCESS[group.id]["members"]
    random.shuffle(player_list)
    GROUP_GAME_PROCESS[group.id]["data"] = {
        "round": 0,
        "player": {
            player: {
                "horse": i,
                "status": {
                    "effect": HorseStatus.Normal,
                    "value": 1,
                    "duration": 0,
                },
                "score": 0,
                "name": (await app.get_member(group.id, player)).name
                if await app.get_member(group.id, player)
                else str(player),
            }
            for i, player in enumerate(player_list, 1)
        },
        "winer": None,
        "cheat": False,
    }

    while True:
        winer = [
            player for player, data in GROUP_GAME_PROCESS[group.id]["data"]["player"].items() if data["score"] >= 100
        ]
        if winer:
            if len(winer) != 1:
                winer = sorted(
                    GROUP_GAME_PROCESS[group.id]["data"]["player"].items(),
                    key=lambda x: x[1]["score"],
                    reverse=True,
                )[0][0]
                GROUP_GAME_PROCESS[group.id]["data"]["winer"] = winer
            else:
                GROUP_GAME_PROCESS[group.id]["data"]["winer"] = winer[0]
            break
        if GROUP_GAME_PROCESS[group.id]["data"]["round"] >= 30:
            MEMBER_RUNING_LIST.remove(member.id)
            GROUP_RUNING_LIST.remove(group.id)
            del GROUP_GAME_PROCESS[group.id]
            return await safeSendGroupMessage(group, MessageChain("游戏进程超长，已结束，没有人获胜"))
        try:
            await asyncio.wait_for(inc.wait(waiter2), timeout=5)  # 等待玩家丢道具
        except asyncio.TimeoutError:
            pass
        last_massage = await safeSendGroupMessage(
            group,
            MessageChain(
                Image(
                    data_bytes=await asyncio.to_thread(
                        draw_game,
                        GROUP_GAME_PROCESS[group.id]["data"],  # 绘制游戏
                    )
                )
            ),
        )
        run_game(GROUP_GAME_PROCESS[group.id]["data"])  # 游戏进程前进
        try:
            await app.recallMessage(GROUP_GAME_PROCESS[group.id]["last_message"])
        except Exception:
            pass
        GROUP_GAME_PROCESS[group.id]["last_message"] = last_massage

    # 结束游戏
    for player, data in GROUP_GAME_PROCESS[group.id]["data"]["player"].items():
        if data["score"] >= 100:
            GROUP_GAME_PROCESS[group.id]["data"]["player"][player].update({"score": 102})
    await asyncio.sleep(3)
    await safeSendGroupMessage(
        group,
        MessageChain(Image(data_bytes=await asyncio.to_thread(draw_game, GROUP_GAME_PROCESS[group.id]["data"]))),
    )
    if GROUP_GAME_PROCESS[group.id]["data"]["cheat"]:
        await safeSendGroupMessage(
            group,
            MessageChain(
                "游戏结束，获胜者是：",
                At(GROUP_GAME_PROCESS[group.id]["data"]["winer"]),
                f" 已获得 {0} {COIN_NAME}",
            ),
        )
    else:
        player_count = len(GROUP_GAME_PROCESS[group.id]["data"]["player"])
        gold_count = (player_count * 5) - player_count
        await asyncio.sleep(1)
        if not random.randint(0, 5):
            del GROUP_GAME_PROCESS[group.id]["data"]["player"][GROUP_GAME_PROCESS[group.id]["data"]["winer"]]
            drop_player = random.choice(list(GROUP_GAME_PROCESS[group.id]["data"]["player"].keys()))
            drop_prop = get_random_prop()
            add_prop(drop_player, drop_prop)
            drop_str = MessageChain("\n本次比赛有一个幸运玩家 ", At(drop_player), f" 获得了 {drop_prop}")
        else:
            drop_str = MessageChain("\n本次比赛没有幸运玩家")
        await safeSendGroupMessage(
            group,
            MessageChain(
                "游戏结束，获胜者是：",
                At(GROUP_GAME_PROCESS[group.id]["data"]["winer"]),
                f" 已获得 {gold_count} {COIN_NAME}",
            )
            + drop_str,
        )
        add_wins(GROUP_GAME_PROCESS[group.id]["data"]["winer"])
        await add_gold(GROUP_GAME_PROCESS[group.id]["data"]["winer"], gold_count)
    MEMBER_RUNING_LIST.remove(member.id)
    GROUP_RUNING_LIST.remove(group.id)
    del GROUP_GAME_PROCESS[group.id]


@channel.use(ListenerSchema(listening_events=[ApplicationShutdowned]))
async def bot_restart():
    for game_group in GROUP_RUNING_LIST:
        if game_group in GROUP_GAME_PROCESS:
            for player in GROUP_GAME_PROCESS[game_group]["members"]:
                await add_gold(player, 5)
            await safeSendGroupMessage(
                game_group,
                MessageChain(
                    [
                        Plain(
                            f"由于 {yaml_data['Basic']['BotName']} 正在重启，本场赛马重置，已补偿所有玩家5个{COIN_NAME}"
                        )
                    ]
                ),
            )


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[
            Twilight(
                [
                    FullMatch("/horse cheat"),
                    "cheat" @ UnionMatch("edit", "add", "上上下下左右左右BA"),
                    "attribute" @ UnionMatch("name", "score", "effect", "value", optional=True),
                    "value" @ ParamMatch(optional=True),
                    "target" @ ParamMatch(optional=True),
                ]
            ),
        ],
        decorators=[
            Function.require("HorseRacing"),
            Permission.require(Permission.MASTER),
            Interval.require(),
        ],
    )
)
async def horse_cheat(
    member: Member,
    group: Group,
    cheat: RegexResult,
    attribute: RegexResult,
    value: RegexResult,
    target: RegexResult,
):
    cheats = cheat.result.display
    if value.matched and target.matched:
        attributes = attribute.result.display
        values = value.result.display
        targets = target.result.display
        if GROUP_GAME_PROCESS[group.id]["status"] == "running":
            players = list(GROUP_GAME_PROCESS[group.id]["data"]["player"].keys())
            logger.info(f"{group.id} {players}")
            if cheats == "edit" and int(targets) <= len(players) and targets.isdigit():
                player = players[int(targets) - 1]
                logger.info(f"{group.id} {player}")
                if attributes == "name":
                    GROUP_GAME_PROCESS[group.id]["data"]["player"][player]["name"] = values
                elif attributes == "score" and values.isdigit():
                    GROUP_GAME_PROCESS[group.id]["data"]["player"][player]["score"] = int(values)
                elif attributes == "effect":
                    GROUP_GAME_PROCESS[group.id]["data"]["player"][player]["status"]["effect"] = values
                    GROUP_GAME_PROCESS[group.id]["data"]["player"][player]["status"]["duration"] = 60
                elif attributes == "value" and values.isdigit():
                    GROUP_GAME_PROCESS[group.id]["data"]["player"][player]["status"]["value"] = int(values)
                else:
                    return await safeSendGroupMessage(group, MessageChain("command error"))
                return await safeSendGroupMessage(group, MessageChain("ok"))

    elif cheats == "ezgame":
        if GROUP_GAME_PROCESS[group.id]["status"] == "running":
            players = list(GROUP_GAME_PROCESS[group.id]["data"]["player"].keys())
            logger.info(f"{group.id} {players}")
            if member.id in players:
                GROUP_GAME_PROCESS[group.id]["data"]["player"][member.id]["status"]["effect"] = "加速"
                GROUP_GAME_PROCESS[group.id]["data"]["player"][member.id]["status"]["duration"] = 60
                GROUP_GAME_PROCESS[group.id]["data"]["player"][member.id]["status"]["value"] = 5
                return await safeSendGroupMessage(group, MessageChain("eeeeeeeez!"))

    await safeSendGroupMessage(group, MessageChain("command error"))


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[
            Twilight([FullMatch("上上下下左右左右BA")]),
        ],
        decorators=[
            Function.require("HorseRacing"),
            Permission.require(),
            Interval.require(),
        ],
    )
)
async def ezgame(member: Member, group: Group):
    if group.id not in GROUP_RUNING_LIST:
        return
    if GROUP_GAME_PROCESS[group.id]["status"] != "running":
        return
    if GROUP_GAME_PROCESS[group.id]["data"]["cheat"]:
        return
    if await reduce_gold(member.id, len(GROUP_GAME_PROCESS[group.id]["data"]["player"]) * 7):
        players = list(GROUP_GAME_PROCESS[group.id]["data"]["player"].keys())
        logger.info(f"{group.id} {players}")
        if member.id in players:
            GROUP_GAME_PROCESS[group.id]["data"]["player"][member.id]["status"]["effect"] = "加速"
            GROUP_GAME_PROCESS[group.id]["data"]["player"][member.id]["status"]["duration"] = 60
            GROUP_GAME_PROCESS[group.id]["data"]["player"][member.id]["status"]["value"] = 3
            GROUP_GAME_PROCESS[group.id]["data"]["cheat"] = True
            await safeSendGroupMessage(group, MessageChain("eeeeeeeez game!"))
            for player in players:
                if player != member.id:
                    await add_gold(player, 5)
    else:
        await safeSendGroupMessage(group, MessageChain("you can`t do this"))
