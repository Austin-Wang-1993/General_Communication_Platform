"""句级英译中辅助 API（中台 §6.9，无场景包绑定）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EnToZhRequest(BaseModel):
    """`POST /translation/en-to-zh` 请求体。"""

    text: str = Field(min_length=1, max_length=8000)


class EnToZhResponse(BaseModel):
    """`POST /translation/en-to-zh` 成功响应。"""

    translated_text: str = Field(min_length=1)
