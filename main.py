#!/usr/bin/env python3.12

import os
import pkgutil
import sys
from asyncio import AbstractEventLoop
from pathlib import Path

import kayaku
from arclet.alconna.avilla import AlconnaAvillaAdapter
from arclet.alconna.graia import AlconnaBehaviour, AlconnaGraiaService
from avilla.core.application import Avilla
from avilla.onebot.v11.protocol import OneBot11ForwardConfig, OneBot11Protocol
from avilla.qqapi.protocol import QQAPIConfig, QQAPIProtocol
from creart import it
from graia.broadcast import Broadcast
from graia.saya import Saya
from graia.scheduler import GraiaScheduler
from graia.scheduler.service import SchedulerService
from graiax.playwright.service import PlaywrightService
from launart import Launart
from loguru import logger
from yarl import URL

from utils.logger_patcher import patch as patch_logger

# 在 import 需要 kayaku 的包前需要先初始化 kayaku
kayaku.initialize({"{**}": "./config/{**}"})
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = Path(__file__).parent.joinpath("cache", "browser").as_posix()

# ruff: noqa: E402
from services import AiohttpClientService, MongoDBService, S3FileService
from services.plugin_init import PluginInitService
from utils.config import BasicConfig
from utils.saya.dispachers import ABotDispatcher

loop = it(AbstractEventLoop)
bcc = it(Broadcast)
saya = it(Saya)
launart = it(Launart)
it(AlconnaBehaviour)

with saya.module_context():
    for module_dir in Path("func").iterdir():
        for module in pkgutil.iter_modules([str(module_dir)]):
            if module.name.startswith("_"):
                continue
            saya.require(f"{module_dir.parent}.{module_dir.name}.{module.name}")

# import 完各种包之后在启动 kayaku
kayaku.bootstrap()

config = kayaku.create(BasicConfig)
kayaku.save_all()

# Avilla 默认添加 MemcacheService
launart.add_component(SchedulerService(it(GraiaScheduler)))
launart.add_component(AiohttpClientService())
launart.add_component(MongoDBService(config.database_uri))
launart.add_component(
    S3FileService(
        config.s3file.endpoint, config.s3file.access_key, config.s3file.secret_key, secure=config.s3file.secure
    )
)
launart.add_component(PluginInitService())
launart.add_component(PlaywrightService())
launart.add_component(AlconnaGraiaService(AlconnaAvillaAdapter, enable_cache=False, global_remove_tome=True))

avilla = Avilla(broadcast=bcc, launch_manager=launart, record_send=config.log_chat)

if not config.protocol.QQAPI.enabled and not config.protocol.OneBot11.enable:
    logger.error("No protocol enabled, please check your configuration.")
    sys.exit()

if config.protocol.QQAPI.enabled:
    avilla.apply_protocols(
        QQAPIProtocol().configure(
            QQAPIConfig(
                config.protocol.QQAPI.id,
                config.protocol.QQAPI.token,
                config.protocol.QQAPI.secret,
                config.protocol.QQAPI.shard,
                config.protocol.QQAPI.intent,
                config.protocol.QQAPI.is_sandbox,
            )
        )
    )
if config.protocol.OneBot11.enable:
    avilla.apply_protocols(
        OneBot11Protocol().configure(
            OneBot11ForwardConfig(URL(config.protocol.OneBot11.forward_url), config.protocol.OneBot11.forward_token)
        )
    )

# 用这种方法重定向 logging 的 Logger 到 loguru 会丢失部分日志 (未解决)
patch_logger(loop, level="DEBUG" if config.debug else "INFO")
del config
bcc.prelude_dispatchers.append(ABotDispatcher)
avilla.launch()

# 可选的: 退出时保存所有配置
# (会导致运行时手动更改的配置文件会被还原)
kayaku.save_all()
