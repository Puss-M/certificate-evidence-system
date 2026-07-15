from typing import Generic, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int
    message: str
    data: DataT | None = None

    @classmethod
    def success(cls, data: DataT | None = None) -> "ApiResponse[DataT]":
        return cls(code=0, message="success", data=data)


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None
