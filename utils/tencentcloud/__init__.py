import kayaku

from utils.config import BasicConfig

from .main import TencentCloudApi

config = kayaku.create(BasicConfig)
tcc = TencentCloudApi(
    config.tencent_cloud.secret_id,
    config.tencent_cloud.secret_key,
)
