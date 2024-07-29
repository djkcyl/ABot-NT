from dataclasses import dataclass, field
from typing import Optional

from avilla.qqapi.protocol import Intents
from kayaku import config
from yarl import URL


@dataclass
class QQAPIConfig:
    enabled: bool = False
    id: str = "undefined"
    """AppID (机器人ID)"""
    token: str = "undefined"
    """Token (机器人令牌)"""
    secret: str = "undefined"
    """AppSecret (机器人密钥)"""
    shard: Optional[tuple[int, int]] = None  # noqa: UP007
    intent: Intents = field(default_factory=Intents)
    is_sandbox: bool = False
    """是否是沙箱环境"""

@dataclass
class OneBot11ForwardConfig:
    forward_url: URL = field(default_factory=URL)
    forward_token: str = "undefined"
    bot_id: str = "undefined"


@dataclass
class Protocol:
    QQAPI: QQAPIConfig = field(default_factory=QQAPIConfig)
    """QQAPI协议配置"""
    OneBot11: OneBot11ForwardConfig = field(default_factory=OneBot11ForwardConfig)

@dataclass
class S3FileConfig:
    endpoint: str = "127.0.0.1:8333"
    access_key: str = ""
    secret_key: str = ""
    secure: bool = True


@dataclass
class TencentCloud:
    secret_id: str = ""
    secret_key: str = ""
    text_biztype: str = ""
    image_biztype: str = ""

@config("main")
class BasicConfig:
    log_chat: bool = True
    """是否将聊天信息打印在日志中"""
    debug: bool = False
    """是否启用调试模式"""
    protocol: Protocol = field(default_factory=Protocol)
    """协议配置"""
    owner: int = 0
    """机器人所有者 AID"""
    database_uri: str = "mongodb://localhost:27017"
    """MongoDB数据库uri"""
    s3file: S3FileConfig = field(default_factory=S3FileConfig)
    """S3文件存储配置"""
    tencent_cloud: TencentCloud = field(default_factory=TencentCloud)
    """腾讯云配置"""
