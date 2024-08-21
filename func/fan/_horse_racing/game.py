import random

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from util.strings import getCutStr

from .gamedata import props, HorseStatus

FONT_PATH = Path("./font")
BASE_PATH = Path(__file__).parent.joinpath("image")


font24 = ImageFont.truetype(str(FONT_PATH.joinpath("sarasa-mono-sc-semibold.ttf")), 24)
ice_img = Image.open(str(BASE_PATH.joinpath("bingkuai_02.png")))
ice_img = ice_img.resize((50, 50))
horse_img = Image.open(str(BASE_PATH.joinpath("horse.png"))).resize((45, 45))
horse1_img = Image.open(str(BASE_PATH.joinpath("horse1.png"))).resize((45, 45))
horse2_img = Image.open(str(BASE_PATH.joinpath("horse2.png"))).resize((45, 45))
horse3_img = Image.open(str(BASE_PATH.joinpath("horse3.png"))).resize((45, 45))


def coloring(img: Image.Image, color):
    img = img.convert("RGBA")
    pixdata = img.load()
    (
        r,
        g,
        b,
    ) = color
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if pixdata[x, y][3] != 0:
                pixdata[x, y] = (r, g, b, pixdata[x, y][3])
    return img


def draw_game(data):
    # color_horse_img = coloring(horse_img, (100, 100, 200))
    color_horse_img = horse3_img
    player_count = len(data["player"])
    arena_size = (500, player_count * 50)
    name_size = (player_count * 24) + ((player_count - 1) * 4)
    img_size = (arena_size[0], arena_size[1] + name_size + 55)
    name_text = "\n".join(
        [
            f"{player['horse']} 号马：{getCutStr(player['name'], 8)}  "
            f"{player['status']['effect']}: {player['status']['duration']}: {player['status']['value']}"
            for _, player in data["player"].items()
        ]
    )
    grass_color = [
        (108, 177, 0),
        (127, 185, 36),
        (108, 177, 0),
        (127, 185, 36),
        (108, 177, 0),
        (127, 185, 36),
        (108, 177, 0),
        (127, 185, 36),
        (108, 177, 0),
    ]
    horse_name = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"]
    image = Image.new("RGB", img_size, (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # 绘制游戏棋盘
    for i, player in enumerate(data["player"], 0):
        # 绘制草块
        draw.rectangle((20, 20 + (50 * i), 480, 20 + (50 * (i + 1))), fill=grass_color[i])
        # 绘制间隔线条
        for n in range(11):
            draw.line(
                (
                    20 + (46 * n),
                    20 + (50 * i),
                    20 + (46 * n),
                    20 + (50 * (i + 1)),
                ),
                fill=(80, 80, 80),
            )
        # 绘制马
        image.paste(
            color_horse_img
            if data["player"][player]["score"] < 100
            else (
                # coloring(horse_img, (255, 0, 0))
                horse3_img
                if data["winer"] == player
                # else coloring(horse_img, (150, 40, 40))
                else color_horse_img
            ),
            (int(22 + ((data["player"][player]["score"] * 4.14))), 22 + (50 * i)),
            color_horse_img,
        )
        # 绘制马的名字
        draw.text(
            (32, 30 + (50 * i)),
            horse_name[data["player"][player]["horse"] - 1],
            font=font24,
            fill=(0, 0, 0),
        )
        # 绘制马的状态
        if data["player"][player]["status"]["effect"] == HorseStatus.Freeze:
            image.paste(
                ice_img,
                (int(18 + ((data["player"][player]["score"] * 4.14))), 14 + (50 * i)),
                ice_img,
            )
    # 绘制边框
    draw.line((20, 20, 480, 20), fill=(80, 80, 80))
    draw.line(
        (20, 20 + (50 * player_count), 480, 20 + (50 * player_count)), fill=(80, 80, 80)
    )
    draw.line(
        (0, arena_size[1] + 40, img_size[0], arena_size[1] + 40), fill="black", width=2
    )
    # 绘制名字
    draw.text((10, arena_size[1] + 45), name_text, (0, 0, 0), font=font24)
    bio = BytesIO()
    image.save(bio, "jpeg")
    return bio.getvalue()


def run_game(data):
    data["round"] += 1
    for player in data["player"]:
        basic_score = random.randint(4, 12) * random.uniform(0.7, 1.2)
        if data["player"][player]["status"]["effect"] == HorseStatus.Death:
            data["player"][player]["status"]["duration"] = None
            data["player"][player]["status"]["value"] = None
            continue
        elif data["player"][player]["status"]["effect"] == HorseStatus.Poisoning:
            if data["player"][player]["status"]["duration"] == 1:
                data["player"][player]["status"]["effect"] = HorseStatus.Death
                data["player"][player]["status"]["duration"] = None
                data["player"][player]["status"]["value"] = None
                continue
            else:
                data["player"][player]["status"]["duration"] -= 1
                basic_score *= 0.8
        else:
            if data["player"][player]["status"]["effect"] in [
                HorseStatus.Freeze,
                HorseStatus.Dizziness,
            ]:
                basic_score = 0
            elif data["player"][player]["status"]["effect"] in [
                HorseStatus.Slowness,
                HorseStatus.SpeedUp,
            ]:
                basic_score *= data["player"][player]["status"]["value"]

            if data["player"][player]["status"]["duration"] > 0:
                data["player"][player]["status"]["duration"] -= 1
            if data["player"][player]["status"]["duration"] == 0:
                data["player"][player]["status"]["effect"] = HorseStatus.Normal
                data["player"][player]["status"]["value"] = 1

        data["player"][player]["score"] += basic_score


def throw_prop(data, target, prop):
    effect, value, duration, _ = props[prop]
    data["player"][target]["status"]["effect"] = effect
    data["player"][target]["status"]["value"] = value
    data["player"][target]["status"]["duration"] = duration
