"""Web app settings from the environment (by their WEBAPP_ names only, so a stray variable cannot set them).

| Variable                | Setting         | Default                          |
|-------------------------|-----------------|----------------------------------|
| `WEBAPP_DIST`           | `web_dist`      | `<repo>/frontend/dist`           |
| `WEBAPP_ALLOWED_HOSTS`  | `allowed_hosts` | `127.0.0.1,localhost,::1`        |
| `WEBAPP_WRITE_CLIENTS`  | `write_clients` | `127.0.0.1,::1,::ffff:127.0.0.1` |

A relative path is resolved against the working directory; an empty variable counts as unset.
"""
from __future__ import annotations

from pathlib import Path

import repo_paths

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO = repo_paths.REPO


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_ignore_empty=True, validate_default=True)

    web_dist: Path = Field(repo_paths.FRONTEND / "dist", validation_alias="WEBAPP_DIST")
    allowed_hosts: str = Field("127.0.0.1,localhost,::1", validation_alias="WEBAPP_ALLOWED_HOSTS",
                               description="comma-separated Host names the app answers (webapp/guard.py: "
                                           "a DNS-rebinding page sends its own name)")
    write_clients: str = Field("127.0.0.1,::1,::ffff:127.0.0.1", validation_alias="WEBAPP_WRITE_CLIENTS",
                               description="comma-separated client addresses whose requests may write "
                                           "(webapp/guard.py): loopback, the end of the SSH tunnel")

    @property
    def hosts(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def writers(self) -> list[str]:
        return [h.strip() for h in self.write_clients.split(",") if h.strip()]

    @field_validator("web_dist")
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        return Path(value).expanduser().resolve()
