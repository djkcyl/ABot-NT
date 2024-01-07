from io import BytesIO
from secrets import token_hex

from avilla.core import Context, Picture, RawResource, UrlResource
from launart import Launart
from PIL import Image

from services import S3FileService


class SelfPicture:
    def __init__(self) -> None:
        self.s3file = Launart.current().get_component(S3FileService).s3file

    async def from_name(self, name: str) -> Picture:
        url = await self.s3file.get_presigned_url(name)
        return Picture(UrlResource(url))

    async def from_data(self, data: bytes | BytesIO, image_format: str | None = None) -> Picture:
        # 如果没有指定格式, 那么就尝试从 data 中获取
        if not image_format:
            if isinstance(data, BytesIO):
                image = Image.open(data)
                data.seek(0)
            else:
                image = Image.open(BytesIO(data))
            if image.format:
                image_format = image.format.lower()
            else:
                msg = "无法获取图片格式"
                raise ValueError(msg)

        # 防止后续操作 data 时出现问题, 先将 data 转换为 bytes
        if isinstance(data, BytesIO):
            data = data.getvalue()
        name = f"{token_hex(32)}.{image_format}"

        # 根据场景选择上传方式
        ctx = Context.current
        if ctx.scene.path_without_land == "group":
            await self.s3file.put_object(name, data, f"image/{image_format}", "temp_image")
            return await self.from_name(name)
        if ctx.scene.path_without_land in {"guild.channel", "guild.user"}:
            return Picture(RawResource(data))
        msg = "不支持的平台"
        raise NotImplementedError(msg)
