from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class CredentialWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: SecretStr = Field(min_length=1, max_length=512)

    @field_validator("secret")
    @classmethod
    def reject_unsafe_secret_text(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw != raw.strip():
            raise ValueError("credential must not have leading or trailing whitespace")
        if any(ord(character) < 32 or ord(character) == 127 for character in raw):
            raise ValueError("credential must not contain control characters")
        return value


class ProviderVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PipelineRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True


class EngineModeWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["pilot", "production"]
    reason: str | None = Field(default=None, max_length=500)


class SignalValidationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_key: Literal["macro_regime_composite", "cross_sectional_momentum"]
