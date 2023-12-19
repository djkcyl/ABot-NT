import asyncio
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from launart import Launart
from loguru import logger
from playwright.async_api._generated import Request, Route
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeElapsedColumn,
    TransferSpeedColumn,
)
from yarl import URL

from services import AiohttpClientService

DEFUALT_DYNAMIC_FONT = "HarmonyOS_Sans_SC_Medium.ttf"


font_path = Path("static", "font")
font_mime_map = {
    "collection": "font/collection",
    "otf": "font/otf",
    "sfnt": "font/sfnt",
    "ttf": "font/ttf",
    "woff": "font/woff",
    "woff2": "font/woff2",
}
font_path.mkdir(parents=True, exist_ok=True)


async def fill_font(route: Route, request: Request):
    url = URL(request.url)
    if not url.is_absolute():
        raise ValueError("字体地址不合法")
    try:
        logger.debug(f"Font {url.name} requested")
        await route.fulfill(
            path=await get_font(url.name),
            content_type=font_mime_map.get(url.suffix),
        )
        return
    except Exception:
        logger.error(f"找不到字体 {url.name}")
        await route.fallback()


async def get_font(font: str = DEFUALT_DYNAMIC_FONT):
    logger.debug(f"font: {font}")
    url = URL(font)
    if url.is_absolute():
        if font_path.joinpath(url.name).exists():
            logger.debug(f"Font {url.name} found in local")
            return font_path.joinpath(url.name)
        else:
            logger.warning(f"字体 {font} 不存在，尝试从网络获取")
            launart = Launart.current()
            session = launart.get_component(AiohttpClientService).session
            resp = await session.get(font)
            if resp.status != 200:
                raise ConnectionError(f"字体 {font} 获取失败")
            font_path.joinpath(url.name).write_bytes(await resp.read())
            return font_path.joinpath(url.name)
    else:
        if not font_path.joinpath(font).exists():
            raise FileNotFoundError(f"字体 {font} 不存在")
        logger.debug(f"Font {font} found in local")
        return font_path.joinpath(font)


def get_font_sync(font: str = DEFUALT_DYNAMIC_FONT):
    return asyncio.run(get_font(font))


# def font_init():
#     # sourcery skip: extract-method
#     font_url = (
#         "https://mirrors.bfsu.edu.cn/pypi/web/packages/ad/97/"
#         "03cd0a15291c6c193260d97586c4adf37a7277d8ae4507d68566c5757a6a/"
#         "bbot_fonts-0.1.1-py3-none-any.whl"
#     )
#     lock_file = Path("data", "font", ".lock")
#     lock_file.touch(exist_ok=True)
#     if lock_file.read_text() != font_url:
#         font_file = BytesIO()
#         with Progress(
#             "{task.description}",
#             BarColumn(),
#             "[progress.percentage]{task.percentage:>3.0f}%",
#             "•",
#             DownloadColumn(),
#             "•",
#             TransferSpeedColumn(),
#             "•",
#             TimeElapsedColumn(),
#         ) as progress_bar:
#             task = progress_bar.add_task("下载字体文件中", start=False)
#             with httpx.stream("GET", font_url) as r:
#                 content_length = int(r.headers["Content-Length"])
#                 progress = 0
#                 progress_bar.update(task, total=content_length)
#                 progress_bar.update(task, completed=0)
#                 for chunk in r.iter_bytes():
#                     font_file.write(chunk)
#                     progress += len(chunk)
#                     percent = progress / content_length * 100
#                     progress_bar.advance(task, advance=percent)
#                 progress_bar.update(task, completed=content_length)
#         with ZipFile(font_file) as z:
#             fonts = [i for i in z.filelist if str(i.filename).startswith("bbot_fonts/font/")]
#             for font in fonts:
#                 file_name = Path(font.filename).name
#                 local_file = font_path.joinpath(file_name)
#                 if not local_file.exists():
#                     logger.info(local_file)
#                     local_file.write_bytes(z.read(font))

#         lock_file.write_text(font_url)
#     else:
#         logger.info("字体文件已存在，跳过下载")
