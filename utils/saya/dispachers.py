from aiohttp import ClientSession
from avilla.core import MessageReceived
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from launart import Launart
from loguru import logger

from services import AiohttpClientService, S3File, S3FileService

from ..db_model import AUser, GroupData
from .model import AGroupBuilder, AUserBuilder


class ABotDispatcher(BaseDispatcher):
    @staticmethod
    async def catch(interface: DispatcherInterface[MessageReceived]):
        ctx = interface.event.context
        if interface.annotation == AUser:
            cid = ctx.client.last_value
            if not await AUser.find_one(AUser.cid == cid):
                last_userid = await AUser.find_one(sort=[("_id", -1)])
                user_id = int(last_userid.aid) + 1 if last_userid else 1
                await AUser(aid=user_id, cid=cid).insert()  # type: ignore
                logger.info(f"[Core.db] 已初始化用户：{cid}")
            user = await AUser.find_one(AUser.cid == cid)
            assert user
            return await AUserBuilder.init(user)
        if interface.annotation == GroupData:
            if ctx.scene.path_without_land in ["guild.channel", "guild.user"]:
                group_id = ctx.scene["guild"]
            else:
                group_id = ctx.scene["group"]
            if not await GroupData.find_one(GroupData.group_id == group_id):
                await GroupData(group_id=group_id).insert()  # type: ignore
                logger.info(f"[Core.db] 已初始化群：{group_id}")
            group = await GroupData.find_one(GroupData.group_id == group_id)
            assert group
            return await AGroupBuilder.init(group)

        manager = Launart.current()
        if interface.annotation == S3File:
            return manager.get_component(S3FileService).s3file

        if interface.annotation == ClientSession:
            return manager.get_component(AiohttpClientService).session
