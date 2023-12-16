from io import BytesIO
from secrets import token_hex

from avilla.core import Picture, UrlResource
from launart import Launart

from services import S3FileService


class SelfPicture:
    def __init__(self):
        self.s3file = Launart.current().get_component(S3FileService).s3file

    async def from_name(self, name: str) -> Picture:
        url = await self.s3file.get_presigned_url(name)
        return Picture(UrlResource(url))

    async def from_data(self, data: bytes | BytesIO, format: str) -> Picture:
        name = f"{token_hex(32)}.{format}"
        await self.s3file.put_object(name, data, f"image/{format}", "temp_image")
        return await self.from_name(name)
