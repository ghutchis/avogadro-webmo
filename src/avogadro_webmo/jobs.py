#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""The "open" feature: pick a job from a table, import it as QC_JSON."""

import json
import logging
import time

from . import config, qcjson
from .client import WebMOError
from .session import connect

logger = logging.getLogger(__name__)

# Cells are joined with this, and the selected row comes back the same way.
DELIMITER = "\t"

HEADERS = ["Job", "Name", "Calculation", "Engine", "Date"]

# --user-options is killed at 30 s. Stop fetching well before that and show a
# short list rather than being killed and showing an empty dialog.
FETCH_BUDGET_SECONDS = 20.0


def user_options(_avo_input=None):
    """Built fresh on every activation, which is the point of "dynamic"."""
    try:
        rows, status = _list_jobs()
    except WebMOError as error:
        return {"userOptions": _status_only(str(error))}
    except Exception:  # a bug here must not leave an empty dialog
        logger.exception("Building the job list failed")
        return {"userOptions": _status_only("Could not build the job list.")}

    if not rows:
        return {"userOptions": _status_only(status)}

    return {
        "userOptions": {
            "Job": {
                "type": "table",
                "order": 1,
                "selectable": True,
                "sortable": True,
                "delimiter": DELIMITER,
                "headers": HEADERS,
                "rows": rows,
                "toolTip": "Pick a job, then press OK to load it.",
            },
            "Status": {"type": "text", "order": 2, "default": status},
        }
    }


def run(avo_input):
    selected = (avo_input.get("options", {}).get("Job") or "").strip()
    if not selected:
        return {"message": "No job selected."}

    number = selected.split(DELIMITER, 1)[0].strip()
    if not number.isdigit():
        return {"message": f"Could not read a job number from {selected!r}."}

    try:
        client = connect()
        metadata = client.job(number)
        status = str(metadata.get("jobStatus", "")).lower()
        if status and status != "complete":
            return {
                "message": (
                    f"Job {number} is {status}, so it has no results to read."
                    + (
                        f"\nFailure code {metadata['failureCode']}."
                        if metadata.get("failureCode")
                        else ""
                    )
                )
            }
        results = client.results(number)
    except WebMOError as error:
        return {"message": str(error)}

    if not results.get("symbols") or not results.get("geometry"):
        return {"message": f"Job {number} returned no structure."}
    if results.get("success") is False:
        return {"message": f"WebMO reports job {number} did not succeed."}

    qcjson.normalize(results, metadata)

    summary = qcjson.summarize(results)
    message = f"Loaded job {number}: {metadata.get('jobName', '')}"
    if summary:
        message += f"\n{summary}"

    # Hand the raw document to Avogadro's own QC_JSON reader rather than
    # converting here. No "bond" key: WebMO supplies connectivity, and asking
    # Avogadro to re-perceive would throw the engine's own bonding away.
    return {
        "moleculeFormat": "qcjson",
        "qcjson": json.dumps(results),
        "message": message,
    }


def _list_jobs():
    """Rows for the table, plus a line describing what is in them."""
    cfg = config.load_config()
    client = connect(cfg)

    filters = {}
    if cfg.get("only_completed", True):
        filters["status"] = "complete"

    numbers = client.jobs(**filters)
    wanted = int(cfg.get("job_count", 25))
    numbers = numbers[:wanted]

    rows = []
    deadline = time.monotonic() + FETCH_BUDGET_SECONDS
    truncated = False
    for number in numbers:
        if time.monotonic() > deadline:
            truncated = True
            break
        try:
            rows.append(_row(number, client.job(number)))
        except WebMOError as error:
            logger.warning("Skipping job %s: %s", number, error)

    where = f"{cfg['username']} @ {cfg['url']}"
    status = f"{len(rows)} of {len(numbers)} recent jobs · {where}"
    if truncated:
        status += (
            f"\nStopped after {FETCH_BUDGET_SECONDS:.0f}s. Lower “Jobs to "
            "list” in Server Settings for a faster list."
        )
    return rows, status


def _row(number, metadata):
    return [
        str(number),
        str(metadata.get("jobName", "")),
        str(metadata.get("jobDescription", "")),
        str(metadata.get("jobEngine", "")),
        str(metadata.get("jobDate", "")),
    ]


def _status_only(message):
    """A form with nothing but an explanation.

    Returning no options at all would make Avogadro treat the command as
    having none and run it immediately, so there is always something here.
    """
    return {"Status": {"type": "text", "order": 1, "default": message}}
