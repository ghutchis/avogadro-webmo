#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""Where the server URL lives, and where the secrets live.

Split deliberately: the URL, username and list preferences are ordinary
settings and go in a JSON file the user can read and edit. The password and
session token go to the OS keychain via `keyring`, with a 0600 file holding
only the token when no keychain is available (headless Linux, mostly).
"""

import json
import logging
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import platformdirs

logger = logging.getLogger(__name__)

SERVICE = "avogadro-webmo"

DEFAULTS = {
    "url": "",
    "username": "",
    "server_version": "",
    "job_count": 25,
    "only_completed": True,
}


def config_path():
    return Path(platformdirs.user_config_dir("avogadro")) / "webmo.json"


def token_fallback_path():
    return Path(platformdirs.user_config_dir("avogadro")) / "webmo-token.json"


# -- ordinary settings -------------------------------------------------------


def read_json(path, default=None):
    """Read a JSON file, treating anything unreadable as simply absent.

    Config and cache files are conveniences; a truncated or hand-edited one is
    never worth a failed dialog.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as error:
        logger.warning("Ignoring unreadable %s: %s", path, error)
        return default


def load_config():
    config = dict(DEFAULTS)
    stored = read_json(config_path())
    if isinstance(stored, dict):
        config.update(stored)
    return config


def save_config(config):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


# -- secrets -----------------------------------------------------------------


def _keyring():
    """Import lazily so a broken keyring never stops the plugin loading."""
    try:
        import keyring

        return keyring
    except Exception as error:  # ImportError, or a backend that explodes
        logger.warning("keyring unavailable: %s", error)
        return None


def _account(config):
    return f"{config.get('username', '')}@{config.get('url', '')}"


def save_password(config, password):
    """Storing the password is what lets an expired token renew silently."""
    keyring = _keyring()
    if keyring is None:
        return False
    try:
        keyring.set_password(SERVICE, _account(config), password)
        return True
    except Exception as error:
        logger.warning("Could not store password in the keychain: %s", error)
        return False


def load_password(config):
    keyring = _keyring()
    if keyring is None:
        return None
    try:
        return keyring.get_password(SERVICE, _account(config))
    except Exception as error:
        logger.warning("Could not read password from the keychain: %s", error)
        return None


def save_token(config, token, hours):
    """Returns True when the keychain took it, False when the file did."""
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    blob = json.dumps({"token": token, "expires": expires.isoformat()})

    keyring = _keyring()
    if keyring is not None:
        try:
            keyring.set_password(SERVICE, _account(config) + "#token", blob)
            _clear_token_fallback()
            return True
        except Exception as error:
            logger.warning("Could not store token in the keychain: %s", error)

    path = token_fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create it private, rather than writing then chmod-ing: the window
    # between the two is exactly when the token is world-readable.
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(blob + "\n")
    return False


def load_token(config):
    """The stored token, or None when it is missing or already expired."""
    blob = None
    keyring = _keyring()
    if keyring is not None:
        try:
            blob = keyring.get_password(SERVICE, _account(config) + "#token")
        except Exception as error:
            logger.warning("Could not read token from the keychain: %s", error)

    stored = json.loads(blob) if blob else read_json(token_fallback_path())
    if not isinstance(stored, dict):
        return None

    try:
        expires = datetime.fromisoformat(stored["expires"])
    except (ValueError, KeyError, TypeError):
        return None

    if expires <= datetime.now(timezone.utc):
        return None
    return stored["token"]


def _clear_token_fallback():
    try:
        token_fallback_path().unlink()
    except OSError:
        pass


def forget(config):
    """Drop both secrets, e.g. when the server or user changes."""
    keyring = _keyring()
    if keyring is not None:
        for account in (_account(config), _account(config) + "#token"):
            try:
                keyring.delete_password(SERVICE, account)
            except Exception:
                # Deleting an entry that was never stored raises, and that is
                # the outcome we wanted anyway.
                pass
    _clear_token_fallback()
