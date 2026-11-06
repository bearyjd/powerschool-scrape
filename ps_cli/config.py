"""Credential loading: env vars > ~/.powersched/.env (KEY=VALUE or legacy 2-line)."""
from __future__ import annotations

import logging
import os
import stat
from urllib.parse import urlparse
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("ps")

DEFAULT_ENV_PATH = Path.home() / ".powersched" / ".env"


class ConfigError(Exception):
    """Configuration problem. Messages never contain credential values."""


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str = field(repr=False)
    base_url: str

    @property
    def host(self) -> str:
        return urlparse(self.base_url).hostname or ""

    def __str__(self) -> str:
        return f"Credentials(username=<redacted>, base_url={self.base_url!r})"

    def __repr__(self) -> str:
        return self.__str__()


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _parse_file(text: str) -> dict[str, str]:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if lines and all("=" in ln for ln in lines):
        out = {}
        for ln in lines:
            k, _, v = ln.partition("=")
            out[k.strip()] = _unquote(v)
        return out
    if len(lines) == 2 and not lines[0].startswith("PS_"):
        return {"PS_USERNAME": lines[0].strip(), "PS_PASSWORD": lines[1].rstrip("\r\n")}
    raise ConfigError("credentials file format not recognised "
                      "(expected KEY=VALUE lines, or 2 lines username/password with PS_BASE_URL in the environment)")


def _read_file(path: Path) -> dict[str, str]:
    try:
        st = path.stat()
        mode, st_uid = stat.S_IMODE(st.st_mode), st.st_uid
        text = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as e:
        raise ConfigError(f"cannot read credentials file: {type(e).__name__}") from None
    if st_uid != os.getuid():
        log.warning("%s is owned by another user (uid %d)", path, st_uid)
    if mode != 0o600:
        log.warning("%s has mode %o; should be 600 (chmod 600)", path, mode)
    return _parse_file(text)


def validate_base_url(url: str, allowed_host: str = "") -> str:
    """Credentials are only ever sent to https://*.powerschool.com (or PS_ALLOWED_HOST)."""
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    ok_host = host.endswith(".powerschool.com") or (bool(allowed_host) and host == allowed_host.lower())
    if parts.scheme != "https" or not ok_host or parts.username or parts.password:
        raise ConfigError("PS_BASE_URL must be https on a *.powerschool.com host "
                          "(or exactly PS_ALLOWED_HOST)")
    return url


def load_credentials(env: dict | None = None, path: Path | None = None) -> Credentials:
    env = os.environ if env is None else env
    path = DEFAULT_ENV_PATH if path is None else path
    needs_file = not (env.get("PS_USERNAME") and env.get("PS_PASSWORD"))
    file_vals = _read_file(path) if needs_file else {}

    def pick(key: str) -> str:
        return env.get(key) or file_vals.get(key) or ""

    username, password = pick("PS_USERNAME"), pick("PS_PASSWORD")
    if not username or not password:
        raise ConfigError("PS_USERNAME / PS_PASSWORD not set (env or ~/.powersched/.env)")
    raw_base = pick("PS_BASE_URL").strip()
    if not raw_base:
        raise ConfigError("PS_BASE_URL not set (env or ~/.powersched/.env); "
                          "e.g. PS_BASE_URL=https://yourdistrict.powerschool.com")
    base = validate_base_url(raw_base.rstrip("/"), pick("PS_ALLOWED_HOST"))
    return Credentials(username, password, base)
