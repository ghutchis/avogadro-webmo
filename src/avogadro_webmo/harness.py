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

DEMO_URL = "https://www.webmo.net/demoserver/cgi-bin/webmo/login.cgi"


def _login(argv):
    url = argv[0] if argv else DEMO_URL
    username = argv[1] if len(argv) > 1 else "guest"
    password = argv[2] if len(argv) > 2 else "guest"

    # Through the real command handler, so this exercises the same validation
    # and storage the dialog does rather than a second copy of it.
    result = settings.run(
        {
            "options": {
                "Server URL": url,
                "Username": username,
                "Password": password,
                "Session length (hours)": 24,
                "Jobs to list": 25,
                "Only completed jobs": True,
            }
        }
    )
    print(result.get("message") or json.dumps(result))
    print(f"  config : {config.config_path()}")


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
