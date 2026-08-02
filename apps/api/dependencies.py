"""FastAPI dependency providers."""

from typing import Annotated

from fastapi import Depends

from apps.api.config import Settings, get_settings

SettingsDependency = Annotated[Settings, Depends(get_settings)]
