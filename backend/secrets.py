from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Literal, Protocol


SecretSource = Literal["keyring", "environment"]


@dataclass(frozen=True)
class SecretValue:
    value: str
    source: SecretSource
    managed: bool


class SecretStoreUnavailable(RuntimeError):
    """Raised when the OS credential store cannot safely accept a secret."""


class SecretStore(Protocol):
    def get(self, credential_name: str, environment_variable: str | None) -> SecretValue | None:
        ...

    def set(self, credential_name: str, secret: str) -> None:
        ...

    def delete(self, credential_name: str) -> bool:
        ...


class KeyringEnvironmentSecretStore:
    """Use the OS credential store, with a read-only environment fallback.

    Environment values are useful for CI and disposable development shells. They
    cannot be created or deleted by the application and are never copied into the
    keyring or SQLite. The keyring dependency is imported lazily so read-only
    deployments can still report an environment-backed credential.
    """

    def __init__(self, service_name: str = "heae.local.operator") -> None:
        self.service_name = service_name

    @staticmethod
    def _keyring():
        try:
            return importlib.import_module("keyring")
        except (ImportError, ModuleNotFoundError) as error:
            raise SecretStoreUnavailable("OS credential storage is unavailable.") from error

    def get(self, credential_name: str, environment_variable: str | None) -> SecretValue | None:
        keyring_failed = False
        try:
            value = self._keyring().get_password(self.service_name, credential_name)
        except Exception:  # Keyring backends expose platform-specific exception classes.
            value = None
            keyring_failed = True
        if value:
            return SecretValue(value=value, source="keyring", managed=True)
        if environment_variable:
            environment_value = os.getenv(environment_variable)
            if environment_value:
                return SecretValue(
                    value=environment_value,
                    source="environment",
                    managed=False,
                )
        if keyring_failed:
            raise SecretStoreUnavailable(
                "The OS credential store could not be read and no environment fallback is configured."
            )
        return None

    def set(self, credential_name: str, secret: str) -> None:
        try:
            self._keyring().set_password(self.service_name, credential_name, secret)
        except Exception as error:
            raise SecretStoreUnavailable(
                "The OS credential store could not save this credential."
            ) from error

    def delete(self, credential_name: str) -> bool:
        try:
            keyring = self._keyring()
            existing = keyring.get_password(self.service_name, credential_name)
            if existing is None:
                return False
            keyring.delete_password(self.service_name, credential_name)
            return True
        except SecretStoreUnavailable:
            raise
        except Exception as error:
            # A missing credential is represented by None above; backend failures
            # must remain distinguishable from an ordinary no-op delete.
            raise SecretStoreUnavailable(
                "The OS credential store could not delete this credential."
            ) from error
