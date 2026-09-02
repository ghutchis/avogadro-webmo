#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""Drive the plugin the way Avogadro does, without launching Avogadro.

    pixi run demo-login  [url] [username] [password]
    pixi run demo-options [settings|open]
    pixi run demo-open   <jobNumber>

Defaults point at the public WebMO demo server (guest/guest).
"""

import json
import sys

from . import config, jobs, settings
from .client import WebMOClient, normalize_url

DEMO_URL = "https://www.webmo.net/demoserver/cgi-bin/webmo/login.cgi"


def _login(argv):
    url = argv[0] if argv else DEMO_URL
    username = argv[1] if len(argv) > 1 else "guest"
    password = argv[2] if len(argv) > 2 else "guest"

    cfg = config.load_config()
    cfg.update(url=normalize_url(url), username=username, session_hours=24)
    client = WebMOClient(cfg["url"], username)
    cfg["server_version"] = client.status().get("version", "")
    client.login(password, 24)

    config.save_config(cfg)
    in_keychain = config.save_token(cfg, client.token, 24)
    config.save_password(cfg, password)
    print(
        f"Signed in to WebMO {cfg['server_version']} as {username}\n"
        f"  config : {config.config_path()}\n"
        f"  token  : {'system keychain' if in_keychain else config.token_fallback_path()}"
    )


def _options(argv):
    feature = argv[0] if argv else "open"
    handler = {"settings": settings, "open": jobs}[feature]
    print(json.dumps(handler.user_options({}), indent=2))


def _open(argv):
    if not argv:
        sys.exit("usage: demo-open <jobNumber>")
    number = argv[0]
    # Fake the row the table would hand back: only field 0 is read.
    row = jobs.DELIMITER.join([number, "", "", "", ""])
    result = jobs.run({"options": {"Job": row}})

    document = result.pop("qcjson", None)
    print(json.dumps(result, indent=2))
    if document is not None:
        parsed = json.loads(document)
        print(f"\nqcjson: {len(document)} bytes, schema {parsed.get('schema_name')}")
        print("properties:", ", ".join(sorted(parsed.get("properties", {}))))


def main():
    commands = {"login": _login, "options": _options, "open": _open}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        sys.exit(f"usage: harness [{'|'.join(commands)}] ...")
    commands[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
