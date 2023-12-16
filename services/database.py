from typing import Any, Literal, cast

from beanie import Document, init_beanie
from beanie.odm.views import View
from launart import Service
from loguru import logger
from motor.core import AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient


class MongoDBService(Service):
    id: str = "database/mongodb_init"
    supported_interface_types: set[Any] = {AgnosticDatabase}

    client: "AgnosticDatabase"

    def __init__(self, uri="mongodb://localhost:27017") -> None:
        super().__init__()
        self.uri = uri

    def get_interface(self, typ: type[AgnosticDatabase]) -> AgnosticDatabase:
        return self.client

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Literal["preparing", "blocking", "cleanup"]]:
        return {"preparing"}

    async def launch(self, _):
        logger.info("Initializing database...")
        self.client = AsyncIOMotorClient(self.uri)["abot"]
        document_models = cast(
            list[type["Document"] | type["View"] | str],
            Document.__subclasses__(),
        )
        await init_beanie(
            database=self.client,
            document_models=document_models,
        )
        logger.success("Database initialized!")

        async with self.stage("preparing"):
            ...
