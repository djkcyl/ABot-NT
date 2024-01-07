from pydantic import BaseModel

from . import ResponseModel


class Location(BaseModel):
    Height: int
    Rotate: int
    Width: int
    X: int
    Y: int


class LabelDetailItem(BaseModel):
    Id: int
    Name: str
    Score: int


class LabelResult(BaseModel):
    Details: list[LabelDetailItem]
    Label: str
    Scene: str
    Score: int
    SubLabel: str
    Suggestion: str


class LibDetail(BaseModel):
    Id: int
    LibId: str
    LibName: str
    ImageId: str
    Label: str
    Tag: str
    Score: int


class LibResult(BaseModel):
    Details: list[LibDetail]
    Label: str
    Scene: str
    Score: int
    SubLabel: str
    Suggestion: str


class ObjectDetail(BaseModel):
    Id: int
    Name: str
    Value: str
    Score: int
    Location: Location
    SubLabel: str
    ObjectId: str


class ObjectResult(BaseModel):
    Details: list[ObjectDetail]
    Label: str
    Names: list[str]
    Scene: str
    Score: int
    SubLabel: str
    Suggestion: str


class OcrTextDetail(BaseModel):
    Keywords: list[str]
    Label: str
    LibId: str
    LibName: str
    Location: Location
    Rate: int
    Score: int
    SubLabel: str
    Text: str


class OcrResult(BaseModel):
    Details: list[OcrTextDetail]
    Label: str
    Scene: str
    Score: int
    SubLabel: str
    Suggestion: str
    Text: str


class RecognitionTag(BaseModel):
    Name: str
    Score: int
    Location: Location


class RecognitionResult(BaseModel):
    Label: str
    Tags: list[RecognitionTag]


class Response(BaseModel):
    BizType: str
    DataId: str
    Extra: None
    FileMD5: str
    Label: str
    LabelResults: list[LabelResult]
    LibResults: list[LibResult]
    ObjectResults: list[ObjectResult]
    OcrResults: list[OcrResult]
    RecognitionResults: list[RecognitionResult]
    RequestId: str
    Score: int
    SubLabel: str
    Suggestion: str


class IMSResponseModel(ResponseModel):
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
