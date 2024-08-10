import ssl
from typing import TYPE_CHECKING

from aiohttp import ClientResponseError, ClientSession
from avilla.core import Message, MessageReceived, Picture
from avilla.standard.qq.elements import Picture
from graia.saya import Channel
from graiax.shortcut import listen, priority
from loguru import logger

from models.saya import FuncType
from services import S3File
from utils.db import AUser, ChatLog, GroupData
from utils.hash import data_md5
from utils.saya import build_metadata

channel = Channel.current()
channel.meta = build_metadata(
    func_type=FuncType.core,
    name="消息日志",
    version="1.2",
    description="记录聊天消息和多媒体数据",
    can_be_disabled=False,
    hidden=True,
)


@listen(MessageReceived)
@priority(1)
async def main(message: Message, auser: AUser, group_data: GroupData, s3f: S3File, asynchttp: ClientSession):  # noqa: ANN201
    message_chain = message.content
    await auser.add_talk()
    await ChatLog.insert(
        ChatLog(
            qid=auser.cid,
            group_id=group_data.group_id,
            message_id=str(message.id),
            message_display=str(message_chain),
        )
    )
    for element in message_chain.include(Picture):
        if TYPE_CHECKING and not isinstance(element, Picture):
            return
        # TODO: 更改获取图片信息的方式
        image_url = element.resource.url

        try:
            for _ in range(3):
                try:
                    if "multimedia.nt.qq.com.cn" in image_url:  # nt.qq.com.cn 的 ssl 版本有问题，需要特殊处理
                        ssl_context = ssl.create_default_context()
                        ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_3
                        ssl_context.set_ciphers("HIGH:!aNULL:!MD5")
                        resp = await asynchttp.get(image_url, ssl=ssl_context)
                    else:
                        resp = await asynchttp.get(image_url)
                    logger.debug(f"[Func.chat_log] 图片 URL: {image_url}")
                    resp.raise_for_status()
                    data = await resp.read()
                    content_type = resp.content_type
                    image_name = f"{data_md5(data)}.{content_type.split('/')[1]}"
                    if await s3f.object_exists(image_name):
                        raise FileExistsError  # noqa: TRY301
                    await s3f.put_object(image_name, data, content_type)
                    logger.success(f"[Func.chat_log] 上传文件 {image_name} 到 S3")
                    break

                except ClientResponseError as e:
                    if e.status != 404:
                        logger.warning(f"[Func.event_log] 无法获取文件 {image_name}，{e.message}，尝试重试")
                        continue
                    logger.warning(f"[Func.event_log] 无法获取文件 {image_name}，{e.message}，跳过")
                    break
                except Exception as e:
                    if isinstance(e, FileExistsError):
                        raise
                    logger.warning(f"[Func.event_log] 无法获取文件 {image_name}，{type(e)} {e}，尝试重试")
                    continue
            else:
                logger.error(f"[Func.chat_log] 无法获取文件 {image_name}，已重试 3 次，跳过")
        except FileExistsError:
            logger.warning(f"[Func.chat_log] 文件 {image_name} 已存在，跳过")