from beanie import Document
from pymongo import IndexModel


class GroupData(Document):
    group_id: str
    disable_functions: list[str] = []
    banned: bool = False

    class Settings:
        name = "core_group"
        indexes = [IndexModel("group_id", unique=True)]
