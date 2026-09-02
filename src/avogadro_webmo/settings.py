#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""The "settings" feature: point at a server, sign in, remember the token."""

from . import cache, config
from .client import WebMOClient, WebMOError, normalize_url


def user_options(_avo_input=None):
    """Built fresh each time so the form shows the current configuration."""
    cfg = config.load_config()
    return {"userOptions": _form(cfg, _describe(cfg))}


def run(avo_input):
    options = avo_input.get("options", {})
    cfg = config.load_config()

    previous = dict(cfg)
    try:
        url = normalize_url(options.get("Server URL", ""))
    except WebMOError as error:
        return {"message": str(error)}

    username = (options.get("Username") or "").strip()
    password = options.get("Password") or ""
    hours = int(options.get("Session length (hours)", 24) or 24)

    if not username:
        return {"message": "A WebMO user name is required."}

    cfg.update(
        url=url,
        username=username,
        session_hours=hours,
        job_count=int(options.get("Jobs to list", 25) or 25),
        only_completed=bool(options.get("Only completed jobs", True)),
    )

    # /status needs no token, so it separates "wrong URL" from "wrong password"
    # long before the login attempt can confuse the two.
    client = WebMOClient(url, username)
    try:
        status = client.status()
    except WebMOError as error:
        return {"message": f"Could not reach that server.\n{error}"}
    cfg["server_version"] = status.get("version", "")

    if not password:
        # Let the user correct a URL or user name without retyping the
        # password, as long as a session is already stored for them.
        if previous.get("url") == url and previous.get("username") == username:
            config.save_config(cfg)
            return {"message": _describe(cfg)}
        return {"message": "A password is required to sign in to WebMO."}

    if previous.get("url") != url or previous.get("username") != username:
        # The stored secrets belong to the old account; they are useless now,
        # and so are that account's cached job listings.
        config.forget(previous)
        cache.forget(previous)

    try:
        client.login(password, hours)
    except WebMOError as error:
        return {"message": f"WebMO refused the sign-in.\n{error}"}

    config.save_config(cfg)
    in_keychain = config.save_token(cfg, client.token, hours)
    config.save_password(cfg, password)

    message = (
        f"Connected to WebMO {cfg['server_version']} as {username}.\n"
        f"The session lasts {hours} hour(s)."
    )
    if not in_keychain:
        message += (
            "\n\nNo system keychain was available, so the token was written to "
            f"{config.token_fallback_path()} (readable only by you). The "
            "password was not stored."
        )
    return {"message": message}


def _describe(cfg):
    if not cfg.get("url"):
        return "Not configured yet."
    signed_in = config.load_token(cfg) is not None
    state = "signed in" if signed_in else "no current session"
    version = cfg.get("server_version") or "unknown version"
    return f"{cfg['username']} @ {cfg['url']}\nWebMO {version}, {state}."


def _form(cfg, status):
    return {
        "Server URL": {
            "type": "string",
            "order": 1,
            "default": cfg.get("url", ""),
            "placeholderText": "https://host/cgi-bin/webmo/rest.cgi",
            "toolTip": "The login page or the cgi-bin directory work too.",
        },
        "Username": {
            "type": "string",
            "order": 2,
            "default": cfg.get("username", ""),
        },
        "Password": {
            "type": "string",
            "order": 3,
            "password": True,
            "toolTip": "Stored in the system keychain, never in a plain file.",
        },
        "Session length (hours)": {
            "type": "integer",
            "order": 4,
            "default": int(cfg.get("session_hours", 24)),
            "minimum": 1,
            "maximum": 168,
        },
        "Jobs to list": {
            "type": "integer",
            "order": 5,
            "default": int(cfg.get("job_count", 25)),
            "minimum": 5,
            "maximum": 100,
            "toolTip": (
                "WebMO returns job numbers only, so each job costs one more "
                "request. Listing more means a longer wait."
            ),
        },
        "Only completed jobs": {
            "type": "boolean",
            "order": 6,
            "default": bool(cfg.get("only_completed", True)),
        },
        "Status": {"type": "text", "order": 7, "default": status},
    }
