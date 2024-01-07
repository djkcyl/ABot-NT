from beanie import Document
from beanie.odm.operators.find.comparison import Eq
from beanie.odm.operators.update.general import Set
from pymongo import IndexModel


class ServerBind(Document):
    group_id: str
    address: str

    class Settings:
        name = "plugin_mcping_bind"
        indexes = [IndexModel("group")]


async def get_bind(group: str | int) -> str | None:
    bind = await ServerBind.find_one(Eq(ServerBind.group_id, str(group)))
    if bind:
        return bind.address
    return None


async def set_bind(group: str | int, address: str) -> None:
    bind = ServerBind.find_one(Eq(ServerBind.group_id, str(group)))
    await bind.upsert(
        Set({ServerBind.address: address}),
        on_insert=ServerBind(group_id=str(group), address=address),
    )


async def delete_bind(group: str | int) -> None:
    await ServerBind.find_one(Eq(ServerBind.group_id, str(group))).delete()
