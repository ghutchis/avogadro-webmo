#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").
#  https://github.com/ghutchis/avogadro-webmo/

"""Entry point for the avogadro-webmo plugin.

Avogadro invokes this as `avogadro-webmo <identifier> [--user-options]` with a
JSON object on stdin, and reads one JSON object back from stdout. Nothing else
may reach stdout, or the parse fails and the command silently does nothing.
"""

import argparse
import json
import logging
import sys
import traceback

# Avogadro expects UTF-8 whatever the console encoding says.
sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger(__name__)

FEATURES = ("settings", "open")


def main():
    parser = argparse.ArgumentParser("avogadro-webmo")
    # Avogadro always passes the feature identifier as the first argument.
    parser.add_argument("feature", nargs="?", default="open")
    parser.add_argument(
        "--user-options",
        action="store_true",
        help="print this feature's option dialog as JSON and exit",
    )
    # Accepted and ignored, but a plugin that rejects them cannot be run.
    parser.add_argument("--lang", nargs="?", default="en")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        stream=sys.stderr,  # never stdout
        format="%(levelname)s %(name)s: %(message)s",
    )

    print(json.dumps(_dispatch(args)))


def _dispatch(args):
    avo_input = _read_input()

    try:
        if args.feature == "settings":
            from . import settings as handler
        elif args.feature == "open":
            from . import jobs as handler
        else:
            return {"error": f"Unknown feature: {args.feature}"}

        if args.user_options:
            # Features whose form is a static JSON file are never asked.
            builder = getattr(handler, "user_options", None)
            if builder is None:
                return {"error": f"{args.feature} has a static option file"}
            return builder(avo_input)
        return handler.run(avo_input)
    except Exception as error:
        logger.exception("avogadro-webmo %s failed", args.feature)
        if args.debug:
            return {"error": "".join(traceback.format_exception(error))}
        return {"error": f"{type(error).__name__}: {error}"}


def _read_input():
    """Avogadro sends "{}" for --user-options and a full object otherwise."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning("Ignoring unparseable stdin (%d bytes)", len(raw))
        return {}
