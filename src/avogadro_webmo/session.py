#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""Turn stored configuration into a logged-in client."""

from . import config
from .client import WebMOAuthError, WebMOClient, WebMOError

NOT_CONFIGURED = (
    "No WebMO server configured.\nRun Extensions › WebMO › Server "
    "Settings… first."
)


def connect(cfg=None):
    """A client with a live token, renewing silently if one is stored.

    Raises WebMOAuthError with something the user can act on when there is no
    way to get a session without them typing a password again.
    """
    cfg = cfg or config.load_config()
    if not cfg.get("url") or not cfg.get("username"):
        raise WebMOAuthError(NOT_CONFIGURED)

    client = WebMOClient(cfg["url"], cfg["username"], config.load_token(cfg))
    if client.token:
        return client

    # The token is missing or has expired. If the password went into the
    # keychain we can renew without bothering the user.
    password = config.load_password(cfg)
    if not password:
        raise WebMOAuthError(
            "The WebMO session has expired.\nRun Extensions › WebMO › "
            "Server Settings… to sign in again."
        )
    hours = int(cfg.get("session_hours", 24))
    client.login(password, hours)
    config.save_token(cfg, client.token, hours)
    return client


__all__ = ["connect", "WebMOAuthError", "WebMOError", "NOT_CONFIGURED"]
