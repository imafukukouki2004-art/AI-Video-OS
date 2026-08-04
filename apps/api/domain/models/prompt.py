from typing import Literal
from uuid import UUID

from pydantic import Field

from apps.api.domain.models.base import DomainModel


class PromptTemplate(DomainModel):
    template: str = Field(..., description="The prompt template string.")
    template_type: Literal["system", "user", "tool"] = Field(..., description="The type of the prompt template.")
    description: str = Field(..., description="A description of the prompt template.")
