from pydantic import BaseModel

from . import ResponseModel


class Tags(BaseModel):
    Keyword: str
    Score: float
    SubLabel: str


class Position(BaseModel):
    Start: int
    End: int


class HitInfo(BaseModel):
    Type: str
    Keyword: str | None
    LibName: str | None
    Positions: list[Position]


class DetailResults(BaseModel):
    Keywords: list[str]
    Label: str
    LibId: str
    LibName: str
    LibType: int
    Score: int
    SubLabel: str
    Suggestion: str
    Tags: list[Tags] | None
    HitInfos: list[HitInfo] | None


class Response(BaseModel):
    BizType: str
    ContextText: str
    DataId: str
    DetailResults: list[DetailResults]
    Extra: str
    Keywords: list[str]
    Label: str
    RequestId: str
    RiskDetails: list[str] | None
    Score: int
    SubLabel: str
    Suggestion: str


class TMSResponseModel(ResponseModel):
    Response: Response

    @property
    def is_safe(self) -> bool:
        "是否安全"
        return self.Response.Suggestion == "Pass"

    @property
    def suggestion(self) -> str:
        "建议"
        return self.Response.Suggestion

    @property
    def label(self) -> str:
        "标签"
        return self.Response.Label

    @property
    def sub_label(self) -> str:
        "子标签"
        return self.Response.SubLabel

    @property
    def mark_problematic_parts(self) -> str:
        "标记问题部分"
        text = self.Response.ContextText
        for detail in self.Response.DetailResults:
            for hit in detail.HitInfos or []:
                for position in hit.Positions:
                    start, end = position.Start, position.End
                    text = text[:start] + "*" * (end - start) + text[end:]
        return text
