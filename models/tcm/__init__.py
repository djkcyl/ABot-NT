from enum import Enum

from pydantic import BaseModel


class ResponseModel(BaseModel):
    retcode: int
    retmsg: dict | str | None
