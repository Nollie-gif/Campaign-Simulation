"""First-boot storage selection with a credential-safe repository fallback."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPOSITORY_MODE = "repository"
SUPABASE_MODE = "supabase"
DEFAULT_SUPABASE_KEY_ENV_VAR = "SUPABASE_KEY"
CONFIGURATION_FIELDS = {
    "storage_mode",
    "supabase_url",
    "supabase_key_env_var",
    "supabase_schema",
    "fallback_reason",
}


def _repository_configuration(reason: str = "") -> dict[str, str]:
    return {
        "storage_mode": REPOSITORY_MODE,
        "supabase_url": "",
        "supabase_key_env_var": "",
        "supabase_schema": "",
        "fallback_reason": reason,
    }


def _write_configuration(config_path: Path, configuration: Mapping[str, str]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=config_path.parent,
        prefix=f".{config_path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(configuration, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"storage configuration requires a non-empty {field}")
    return value


def _is_valid_supabase_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_storage_configuration(configuration: Mapping[str, object]) -> dict[str, str]:
    """Validate persisted configuration without ever accepting a secret value."""

    if not isinstance(configuration, Mapping):
        raise ValueError("storage configuration must be an object")
    unexpected = set(configuration) - CONFIGURATION_FIELDS
    if unexpected:
        raise ValueError("storage configuration contains unsupported or secret fields")

    mode = configuration.get("storage_mode")
    if mode == REPOSITORY_MODE:
        reason = configuration.get("fallback_reason", "")
        if not isinstance(reason, str):
            raise ValueError("storage configuration fallback_reason must be a string")
        return _repository_configuration(reason)
    if mode != SUPABASE_MODE:
        raise ValueError("storage configuration mode is invalid")

    url = _require_text(configuration.get("supabase_url"), "supabase_url")
    if not _is_valid_supabase_url(url):
        raise ValueError("storage configuration Supabase URL must use HTTPS")
    key_env_var = _require_text(configuration.get("supabase_key_env_var"), "supabase_key_env_var")
    schema = configuration.get("supabase_schema", "")
    if not isinstance(schema, str):
        raise ValueError("storage configuration supabase_schema must be a string")
    fallback_reason = configuration.get("fallback_reason", "")
    if not isinstance(fallback_reason, str):
        raise ValueError("storage configuration fallback_reason must be a string")
    return {
        "storage_mode": SUPABASE_MODE,
        "supabase_url": url,
        "supabase_key_env_var": key_env_var,
        "supabase_schema": schema,
        "fallback_reason": fallback_reason,
    }


def probe_supabase(url: str, api_key: str, timeout_seconds: float = 5.0) -> bool:
    """Perform a low-impact authenticated settings probe against Supabase."""

    endpoint = f"{url.rstrip('/')}/auth/v1/settings"
    request = Request(
        endpoint,
        headers={"apikey": api_key, "Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - user-selected HTTPS URL
            return 200 <= response.status < 300
    except (HTTPError, URLError, ValueError, OSError):
        return False


def _probe_external_store(probe: Callable[..., bool], url: str, api_key: str) -> bool:
    try:
        return bool(probe(url, api_key))
    except TypeError:
        # Retain compatibility with the original one-argument adapter contract.
        try:
            return bool(probe(url))
        except Exception:
            return False
    except Exception:
        return False


def _activate_supabase_or_fallback(
    candidate: Mapping[str, object],
    environment: Mapping[str, str],
    external_probe: Callable[..., bool] | None,
) -> dict[str, str]:
    try:
        configuration = validate_storage_configuration(candidate)
    except ValueError as error:
        return _repository_configuration(f"Supabase configuration was invalid: {error}")

    if configuration["storage_mode"] == REPOSITORY_MODE:
        return configuration

    api_key = environment.get(configuration["supabase_key_env_var"], "")
    if not isinstance(api_key, str) or not api_key.strip():
        return _repository_configuration("Supabase credential environment variable is unavailable")
    probe = external_probe or probe_supabase
    if not _probe_external_store(probe, configuration["supabase_url"], api_key):
        return _repository_configuration("Supabase connection was unavailable or rejected")
    configuration["fallback_reason"] = ""
    return configuration


def _read_persisted_configuration(config_path: Path) -> Mapping[str, object]:
    try:
        configuration = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("stored storage configuration is not valid JSON") from error
    if not isinstance(configuration, Mapping):
        raise ValueError("stored storage configuration must be an object")
    return configuration


def resolve_storage_mode(
    config_path: Path,
    input_fn=input,
    external_probe: Callable[..., bool] | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a validated local preference with safe repository fallback.

    A stored configuration is never re-prompted. Invalid, unavailable, or
    credential-less Supabase settings are replaced with a persisted repository
    fallback so the simulation can always continue.
    """

    effective_environment = environment if environment is not None else os.environ
    if config_path.exists():
        try:
            persisted = _read_persisted_configuration(config_path)
        except ValueError as error:
            result = _repository_configuration(f"Stored storage configuration was invalid: {error}")
        else:
            result = _activate_supabase_or_fallback(persisted, effective_environment, external_probe)
        _write_configuration(config_path, result)
        return result

    answer = input_fn("Storage mode [repository/supabase] (repository): ").strip().lower()
    if answer != SUPABASE_MODE:
        result = _repository_configuration()
        _write_configuration(config_path, result)
        return result

    url = input_fn("Supabase URL (HTTPS): ").strip()
    key_env_var = input_fn(
        f"Supabase API key environment variable ({DEFAULT_SUPABASE_KEY_ENV_VAR}): "
    ).strip() or DEFAULT_SUPABASE_KEY_ENV_VAR
    result = _activate_supabase_or_fallback(
        {
            "storage_mode": SUPABASE_MODE,
            "supabase_url": url,
            "supabase_key_env_var": key_env_var,
            "supabase_schema": "",
            "fallback_reason": "",
        },
        effective_environment,
        external_probe,
    )
    _write_configuration(config_path, result)
    return result
