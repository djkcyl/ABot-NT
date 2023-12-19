import asyncio
import hashlib
import re
from base64 import b64encode
from datetime import datetime, timedelta
from io import BytesIO

from graiax.text2img.playwright import (
    HTMLRenderer,
    MarkdownConverter,
    PageOption,
    ScreenshotOption,
    convert_text,
)
from graiax.text2img.playwright.renderer import BuiltinCSS
from jinja2 import Template
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api._generated import Request
from qrcode.constants import ERROR_CORRECT_L
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from qrcode.main import QRCode

from core_bak.data_file import get_data_path

from .fonts_provider import fill_font
from .strings import get_cut_str


def network_requestfailed(request: Request):
    url = request.url
    fail = request.failure
    method = request.method
    logger.warning(f"[RequestFailed] [{method} {fail}] << {url}")


font_file = "./static/font/sarasa-mono-sc-semibold.ttf"
font = ImageFont.truetype(font_file, 22)
cache = get_data_path("cache", "t2i")
cache.mkdir(exist_ok=True, parents=True)


qrcode = QRCode(image_factory=StyledPilImage)
qrcode.add_data("https://qun.qq.com/qunpro/robot/share?robot_appid=101985270")
invite_guild: Image.Image = qrcode.make_image(fill_color="black", back_color="#eee").get_image().resize((100, 100))

qrcode.clear()
qrcode.add_data("https://qun.qq.com/qunpro/robot/qunshare?robot_appid=101985270&robot_uin=2854214511")
invite_group: Image.Image = qrcode.make_image(fill_color="black", back_color="#eee").get_image().resize((100, 100))

# 把两张二维码横向拼接在一起
invite_qr = Image.new("RGB", (invite_guild.width + invite_group.width + 10, invite_guild.height), "#eee")
invite_qr.paste(invite_guild, (0, 0))
invite_qr.paste(invite_group, (invite_guild.width + 10, 0))
imageio = BytesIO()
invite_qr.save(imageio, format="PNG")
b64 = b64encode(imageio.getvalue()).decode()


def footer():
    return (
        "<style>.footer{box-sizing:border-box;position:absolute;left:0;width:100%;background:#eee;"
        "padding:30px 40px;margin-top:40px;font-size:1.3rem;color:#6b6b6b;}"
        ".footer p{margin:5px auto;}</style>"
        '<div class="footer">'
        f'<img align="right" src="data:image/png;base64,{b64}" />'
        "<p>由 ABot 生成</p>"
        "<br/>"
        f'<p>{datetime.now().strftime("%Y/%m/%d %p %I:%M:%S")}</p>'
        f"</div>"
    )


html_render = HTMLRenderer(
    page_option=PageOption(device_scale_factor=1.5),
    screenshot_option=ScreenshotOption(type="jpeg", quality=80, full_page=True, scale="device"),
    css=(
        BuiltinCSS.reset,
        BuiltinCSS.github,
        BuiltinCSS.one_dark,
        BuiltinCSS.container,
        "@font-face{font-family:'harmo';font-weight:300;"
        "src:url('http://font.static.abot/HarmonyOS_Sans_SC_Light.ttf') format('truetype');}"
        "@font-face{font-family:'harmo';font-weight:400;"
        "src:url('http://font.static.abot/HarmonyOS_Sans_SC_Regular.ttf') format('truetype');}"
        "@font-face{font-family:'harmo';font-weight:500;"
        "src:url('http://font.static.abot/HarmonyOS_Sans_SC_Medium.ttf') format('truetype');}"
        "@font-face{font-family:'harmo';font-weight:600;"
        "src:url('http://font.static.abot/HarmonyOS_Sans_SC_Bold.ttf') format('truetype');}"
        "*{font-family:'harmo',sans-serif}",
    ),
    page_modifiers=[
        lambda page: page.route(re.compile("^http://font.static.abot/(.+)$"), fill_font),
        # lambda page: page.on("requestfailed", network_requestfailed),
    ],
)

md_converter = MarkdownConverter()


async def create_image(text: str, cut=64, playwright=False) -> bytes:
    str_hash = hashlib.md5(text.encode("utf-8")).hexdigest() + "html" if playwright else ""
    cache.joinpath(str_hash[:2]).mkdir(exist_ok=True)
    cache_file = cache.joinpath(f"{str_hash}.jpg")
    if cache_file.exists():
        logger.info(f"T2I Cache hit: {str_hash}")
        image_bytes = cache_file.read_bytes()
    else:
        if playwright:
            image_bytes = await _create_playwright_image(text, cut)
        else:
            image_bytes = await asyncio.to_thread(_create_pil_image, text, cut)
        cache_file.write_bytes(image_bytes)

    return image_bytes


def _create_pil_image(text: str, cut: int) -> bytes:
    cut_str = "\n".join(get_cut_str(text, cut))
    text_box = font.getbbox(cut_str)
    textx = text_box[2] - text_box[0]
    texty = text_box[3] - text_box[1]
    image = Image.new("RGB", (textx + 40, texty + 40), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), cut_str, font=font, fill=(31, 31, 33))
    imageio = BytesIO()
    image.save(
        imageio,
        format="JPEG",
        quality=90,
        subsampling=2,
        qtables="web_high",
    )
    return imageio.getvalue()


async def _create_playwright_image(text: str, cut: int) -> bytes:
    return await HTMLRenderer().render(convert_text(text))


def delete_old_cache():
    cache_files = cache.glob("*")
    i = 0
    r = 0
    for cache_file in cache_files:
        i += 1
        if cache_file.stat().st_mtime < ((datetime.now() - timedelta(days=14)).timestamp()) and cache_file.is_file():
            cache_file.unlink()
            logger.info(f"[Util.t2i] 删除过期缓存：{cache_file}")
            r += 1
    return i, r


async def text2img(text: str, width: int = 800) -> bytes:
    html = convert_text(text)
    html += footer()

    return await html_render.render(
        html,
        extra_page_option=PageOption(viewport={"width": width, "height": 10}),
    )


async def md2img(text: str, width: int = 800) -> bytes:
    html = md_converter.convert(text)
    html += footer()

    return await html_render.render(
        html,
        extra_page_option=PageOption(viewport={"width": width, "height": 10}),
    )


async def template2img(
    template: str,
    render_option: dict[str, str],
    *,
    extra_page_option: PageOption | None = None,
    extra_screenshot_option: ScreenshotOption | None = None,
) -> bytes:
    """Jinja2 模板转图片
    Args:
        template (str): Jinja2 模板
        render_option (Dict[str, str]): Jinja2.Template.render 的参数
        return_html (bool): 返回生成的 HTML 代码而不是图片生成结果的 bytes
        extra_page_option (PageOption, optional): Playwright 浏览器 new_page 方法的参数
        extra_screenshot_option (ScreenshotOption, optional): Playwright 浏览器页面截图方法的参数
        extra_page_methods (Optional[List[Callable[[Page], Awaitable]]]):
            默认为 None，用于 https://playwright.dev/python/docs/api/class-page 中提到的部分方法，
            如 `page.route(...)` 等
    """
    html_code: str = Template(template).render(**render_option)
    return await html_render.render(
        html_code,
        extra_page_option=extra_page_option,
        extra_screenshot_option=extra_screenshot_option,
    )
