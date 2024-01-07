import asyncio
import hashlib
import random
import re
from base64 import b64encode
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from graiax.text2img.playwright import (
    HTMLRenderer,
    MarkdownConverter,
    PageOption,
    ScreenshotOption,
    convert_text,
)
from graiax.text2img.playwright.renderer import BuiltinCSS
from jinja2 import Template
from launart import Launart
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api._generated import Request
from qrcode.image.styledpil import StyledPilImage
from qrcode.main import QRCode

from core_bak.data_file import get_data_path
from models.ad import AdvertisementCategory
from services import AiohttpClientService, S3FileService
from utils.builder import ADBuilder
from utils.datetime import CHINA_TZ

from .fonts_provider import fill_font
from .strings import get_cut_str

# 广告出现的概率
DEFAULT_AD_PROBABILITY = 0.7

font_file = "./static/font/sarasa-mono-sc-semibold.ttf"
font = ImageFont.truetype(font_file, 22)
cache = get_data_path("cache", "t2i")
cache.mkdir(exist_ok=True, parents=True)

qrcode = QRCode(image_factory=StyledPilImage)
qrcode.add_data("https://qun.qq.com/qunpro/robot/share?robot_appid=101985270")
invite_guild: Image.Image = qrcode.make_image(fill_color="black", back_color="#fafafac0").get_image().resize((200, 200))
bio = BytesIO()
invite_guild.save(bio, format="PNG")
guild_b64 = b64encode(bio.getvalue()).decode()

qrcode.clear()
qrcode.add_data("https://qun.qq.com/qunpro/robot/qunshare?robot_appid=101985270&robot_uin=2854214511")
invite_group: Image.Image = qrcode.make_image(fill_color="black", back_color="#fafafac0").get_image().resize((200, 200))
bio = BytesIO()
invite_group.save(bio, format="PNG")
group_b64 = b64encode(bio.getvalue()).decode()


footer_css = Path("./static/css/footer.css").read_text()

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
        "body{background-color:#fafafac0;}",
        "@media(prefers-color-scheme:light){.markdown-body{--color-canvas-default:#fafafac0;}}",
        footer_css,
    ),
    page_modifiers=[
        lambda page: page.route(re.compile("^http://font.static.abot/(.+)$"), fill_font),
        # lambda page: page.on("requestfailed", network_requestfailed),
    ],
)

md_converter = MarkdownConverter()


def network_requestfailed(request: Request) -> None:
    url = request.url
    fail = request.failure
    method = request.method
    logger.warning(f"[RequestFailed] [{method} {fail}] << {url}")


async def add_footer(
    category: AdvertisementCategory = AdvertisementCategory.announcement,
    target_audience: list | None = None,
) -> str:
    if target_audience is None:
        target_audience = []
    ad = await ADBuilder.get_ad(category, target_audience=target_audience)
    if random.random() > DEFAULT_AD_PROBABILITY and ad:
        ad_type = ad.ad_category.value
        if ad.content_type == 0:
            ad_p = "<p>" + "</p><p>".join(ad.content.splitlines()) + "</p>"
            ad_html = (
                "<style>.ad-text::before{content: '" + ad_type + "'}</style>"
                f'<div class="ad-text"><div class="text-area">{ad_p}</div></div>'
            )
        else:
            s3file = Launart.current().get_component(S3FileService).s3file
            ad_image = await s3file.get_object(ad.content)
            ad_base64 = b64encode(await ad_image.read()).decode()
            ad_html = (
                "<style>.ad-img::before{content: '" + ad_type + "'}</style>"
                f'<div class="ad-img"><img src="data:image/png;base64,{ad_base64}"/></div>'
            )
    else:
        ad_type = "一言"
        session = Launart.current().get_component(AiohttpClientService).session
        async with session.get("https://v1.hitokoto.cn/?encode=text") as resp:
            yiyan = await resp.text()
        ad_html = (
            "<style>.ad-text::before{content: '" + ad_type + "'}</style>"
            f'<div class="ad-text"><div class="text-area">{yiyan}</div></div>'
        )

    return f"""
    <div style="position:absolute;left:0;width:100%">
        <footer>
            <section class="left">
                <div class="footer-text">
                    <p style="font-weight: bold">该图片由 ABot 生成</p>
                    <p style="font-size: 14px">{datetime.now(CHINA_TZ).strftime("%Y/%m/%d %p %I:%M:%S")}</p>
                </div>
                <section class="ad">{ad_html}</section>
            </section>
            <section class="right">
                <div class="qrcode-area">
                    <img class="qrcode" src="data:image/png;base64,{group_b64}" />
                    <img class="qrcode" src="data:image/png;base64,{guild_b64}" />
                </div>
                <div class="qrcode-text">
                    <p>扫描二维码将 ABot 添加至你的群聊/频道</p>
                </div>
            </section>
        </footer>
        <section class="powered">Powered by Avilla</section>
    </div>
    """


async def create_image(text: str, cut: int = 64) -> bytes:
    str_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cache.joinpath(str_hash[:2]).mkdir(exist_ok=True)
    cache_file = cache.joinpath(f"{str_hash}.jpg")
    if cache_file.exists():
        logger.info(f"T2I Cache hit: {str_hash}")
        image_bytes = cache_file.read_bytes()
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


def delete_old_cache() -> tuple[int, int]:
    cache_files = cache.glob("*")
    i = 0
    r = 0
    for cache_file in cache_files:
        i += 1
        if (
            cache_file.stat().st_mtime < ((datetime.now(CHINA_TZ) - timedelta(days=14)).timestamp())
            and cache_file.is_file()
        ):
            cache_file.unlink()
            logger.info(f"[Util.t2i] 删除过期缓存: {cache_file}")
            r += 1
    return i, r


async def html2img(
    html: str,
    page_option: PageOption | None = None,
    screenshot_option: ScreenshotOption | None = None,
) -> bytes:
    html += await add_footer()
    return await html_render.render(
        html,
        extra_page_option=page_option,
        extra_screenshot_option=screenshot_option,
    )


async def text2img(text: str, width: int = 800) -> bytes:
    html = convert_text(text)
    html += await add_footer()

    return await html_render.render(
        html,
        extra_page_option=PageOption(viewport={"width": width, "height": 10}),
    )

async def html2img(html: str, width: int = 800) -> bytes:
    html += await add_footer()

    return await html_render.render(
        html,
        extra_page_option=PageOption(viewport={"width": width, "height": 10}),
    )


async def md2img(text: str, width: int = 800) -> bytes:
    html = md_converter.convert(text)
    return await html2img(html, width)


async def template2img(
    template: str | Template,
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
            默认为 None, 用于 https://playwright.dev/python/docs/api/class-page 中提到的部分方法,
            如 `page.route(...)` 等
    """
    if isinstance(template, Template):
        html_code = template.render(**render_option)
    else:
        html_code = Template(template).render(**render_option)
    return await html_render.render(
        html_code,
        extra_page_option=extra_page_option,
        extra_screenshot_option=extra_screenshot_option,
    )
