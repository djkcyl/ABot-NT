import secrets
from datetime import timedelta
from io import BytesIO

from aiohttp import ClientResponse
from launart import Launart, Service
from loguru import logger
from miniopy_async import Minio
from miniopy_async.commonconfig import Tags
from miniopy_async.error import S3Error
from miniopy_async.helpers import ObjectWriteResult

from services.aiohttp import AiohttpClientService


class S3FileError(Exception):
    pass


class S3File(Minio):
    async def get_object(self, object_name: str) -> ClientResponse:
        launart = Launart.current()
        session = launart.get_component(AiohttpClientService).session
        return await super().get_object("abot7f8befa44d10", object_name, session)

    async def put_object(
        self,
        object_name: str,
        data: bytes | BytesIO,
        content_type: str = "application/octet-stream",
        o_type: str | None = None,
    ) -> ObjectWriteResult:
        if isinstance(data, bytes):
            readble = BytesIO(data)
            legnth = len(data)
        elif isinstance(data, BytesIO):
            readble = data
            legnth = data.getbuffer().nbytes
        else:
            msg = "data must be bytes or BytesIO"
            raise TypeError(msg)

        readble.seek(0)

        tags = Tags()
        if o_type:
            tags["O_Type"] = o_type

        return await super().put_object("abot7f8befa44d10", object_name, readble, legnth, content_type, tags=tags)

    async def object_exists(self, object_name: str) -> bool:
        try:
            await self.get_object(object_name)
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise
        return True

    async def list_objects(self, prefix: str) -> list | None:
        return await super().list_objects("abot7f8befa44d10", prefix)

    async def get_presigned_url(self, object_name: str, expires_seconds: int = 300) -> str:
        return await super().get_presigned_url(
            "GET", "abot7f8befa44d10", object_name, timedelta(seconds=expires_seconds)
        )

    async def remove_object(self, object_name: str) -> None:
        return await super().remove_object("abot7f8befa44d10", object_name)

    async def set_object_tags(self, object_name: str, tag: Tags | dict[str, str]) -> None:
        if isinstance(tag, dict):
            tags = Tags()
            tags.update(tag)
        return await super().set_object_tags("abot7f8befa44d10", object_name, tags)


class S3FileService(Service):
    id: str = "abot/s3file"

    def __init__(
        self,
        endpoint: str = "127.0.0.1:8333",
        access_key: str | None = None,
        secret_key: str | None = None,
        *,
        secure: bool = False,
    ) -> None:
        super().__init__()
        self.s3file = S3File(endpoint, access_key, secret_key, secure=secure)

    # def get_interface(self, _) -> Minio:
    #     return self.s3file

    @property
    def required(self) -> set:
        return set()

    @property
    def stages(self) -> set[str]:
        return {"preparing"}

    async def launch(self, _: Launart) -> None:
        async with self.stage("preparing"):
            if await self.s3file.bucket_exists("abot7f8befa44d10"):
                logger.info("S3 Bucket 已存在")
            else:
                logger.info("正在创建 S3 Bucket")
                await self.s3file.make_bucket("abot7f8befa44d10")
                logger.success("S3 Bucket 创建成功")

            test_text = secrets.token_hex(16).encode()
            if await self.s3file.object_exists(".keep"):
                await self.s3file.remove_object(".keep")
            put_test = await self.s3file.put_object(".keep", test_text)
            if put_test:
                logger.info("S3 Bucket 可写")
            else:
                logger.error("S3 Bucket 不可写")
                msg = "S3 Bucket 不可写"
                raise S3FileError(msg)
            read_test: ClientResponse = await self.s3file.get_object(".keep")
            if await read_test.read() == test_text:
                logger.info("S3 Bucket 可读")
            else:
                logger.error("S3 Bucket 不可读")
                msg = "S3 Bucket 不可读"
                raise S3FileError(msg)

            logger.success("S3 Bucket 测试完成")
