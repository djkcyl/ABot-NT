import asyncio
import secrets

import kayaku
from graia.amnesia.builtins.memcache import MemcacheService
from launart import Launart, Service
from loguru import logger

from utils.config import BasicConfig


class PluginInitService(Service):
    id = "abot/plugin_init"

    @property
    def stages(self) -> set[str]:
        return {"preparing", "blocking","cleanup"}

    @property
    def required(self) -> set[str]:
        return {"abot/mongodb", "abot/s3file"}

    async def launch(self, launart: Launart) -> None:
        async with self.stage("preparing"):
            pass
        async with self.stage("blocking"):
            config = kayaku.create(BasicConfig)
            memcach = launart.get_component(MemcacheService).cache
            exit_mark = asyncio.create_task(launart.status.wait_for_sigexit())
            if config.owner:
                logger.info(f"Owner already set. AID:{config.owner}")
            else:
                owner_init_code = secrets.token_hex(8)
                await memcach.set("owner_init_code", owner_init_code)
                logger.info(f"Owner init code: {owner_init_code}")
                await asyncio.sleep(10)
                if await memcach.get("owner_init_code"):
                    while not exit_mark.done():
                        logger.warning(f"Owner init code not used: {owner_init_code}")
                        await asyncio.sleep(5)
                        if not await memcach.get("owner_init_code"):
                            break
        async with self.stage("cleanup"):
            pass
