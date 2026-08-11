"""Value models for runtime prompt composition."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PromptTemplate(BaseModel):
    """A typed prompt template supplied by workflow configuration."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    template: str = Field(min_length=1)
    template_type: Literal["system", "user"]
    description: str | None = None


class PromptComposition(BaseModel):
    """Resolved prompts ready to pass through the provider interface."""

    model_config = ConfigDict(frozen=True)

    user_prompt: str
    system_prompt: str | None = None
