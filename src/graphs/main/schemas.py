from typing import TypedDict
from pydantic import BaseModel, Field

from src.enums import PMNextStep


class CustomMessage(TypedDict):
    message: str


class PMOutput(BaseModel):
    next_step: PMNextStep = Field(default=PMNextStep.END, description="下一步要做的事情，参考PMNextStep枚举类")
    message: str = Field(description="给客户的回话，或者给下一步任务的指示")
