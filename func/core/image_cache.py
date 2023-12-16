import asyncio
from io import BytesIO

from aiohttp import ClientResponseError, ClientSession
from avilla.core import MessageChain, MessageReceived, Picture
from graia.saya import Channel
from graiax.shortcut import listen, priority
from loguru import logger

from services import S3File
from utils.saya import build_metadata
from utils.saya.model import AUser, FuncType

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.core,
    name="图片缓存",
    version="1.1",
    description="缓存 Bot 收到的图片到 S3",
    can_be_disabled=False,
    hidden=True,
)


@listen(MessageReceived)
@priority(1)
async def main(message: MessageChain, auser: AUser, s3f: S3File, asynchttp: ClientSession):
    await auser.add_talk()
    for element in message.include(Picture):
        element: Picture
        image_url = element.resource.url
        image_name = element.resource.filename
        content_type = element.resource.content_type
        print(image_url, image_name)
        if await s3f.object_exists(image_name):
            continue

        for _ in range(3):
            try:
                resp = await asynchttp.get(image_url)
                resp.raise_for_status()
                data = await resp.read()
                content_type = resp.content_type or content_type
                await s3f.put_object(image_name, data, content_type)
                logger.success(f"[Func.chat_log] 上传文件 {image_name} 到 S3")
                break

            except ClientResponseError as e:
                if e.status != 404:
                    logger.warning(f"[Func.event_log] 无法获取文件 {image_name}，{e.message}，尝试重试")
                    continue
                else:
                    logger.warning(f"[Func.event_log] 无法获取文件 {image_name}，{e.message}，跳过")
                    break
        else:
            logger.error(f"[Func.chat_log] 无法获取文件 {image_name}，已重试 3 次，跳过")
