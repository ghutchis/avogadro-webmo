#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""A local memo of job metadata, because WebMO makes it expensive.

/jobs returns job *numbers* only, so every row of the picker costs another
request at roughly 0.4 s, and the server serializes them -- a thread pool
measured no faster than doing them one at a time. A finished job never changes
again, though, so it only ever has to be fetched once.
"""

import hashlib
import json
import logging
import re
import urllib.parse
from pathlib import Path

import platformdirs

from .config import read_json

logger = logging.getLogger(__name__)

# A job in one of these states is finished for good and safe to keep. Anything
# else -- running, queued -- is asked about again every time.
TERMINAL_STATES = {"complete", "failed"}

# Job numbers rise monotonically, so "drop the lowest" is "drop the oldest".
MAX_ENTRIES = 2000

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def cache_path(cfg):
    """One file per server *and* user; the hash separates two installs on the
    same host, which the readable part of the name cannot."""
    url = cfg.get("url", "")
    user = cfg.get("username", "")
    host = urllib.parse.urlsplit(url).netloc or "unknown"
    digest = hashlib.sha256(f"{url}\n{user}".encode()).hexdigest()[:8]
    stem = f"{_UNSAFE.sub('_', host)}-{_UNSAFE.sub('_', user)}-{digest}"
    return Path(platformdirs.user_cache_dir("avogadro")) / "webmo" / f"{stem}.json"


class JobCache:
    """Job number (as a string) -> the metadata block WebMO returned."""

    def __init__(self, path, entries=None):
        self.path = path
        self.entries = entries or {}
        self.hits = 0
        self.misses = 0
        self._dirty = False

    @classmethod
    def load(cls, cfg):
        path = cache_path(cfg)
        entries = read_json(path)
        return cls(path, entries if isinstance(entries, dict) else {})

    def get(self, number):
        metadata = self.entries.get(str(number))
        if metadata is None:
            self.misses += 1
            return None
        self.hits += 1
        return metadata

    def put(self, number, metadata):
        """Only finished jobs are kept; a running one would go stale at once."""
        status = str(metadata.get("jobStatus", "")).lower()
        if status not in TERMINAL_STATES:
            return
        self.entries[str(number)] = metadata
        self._dirty = True

    def save(self):
        if not self._dirty:
            return
        self._evict()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.entries, separators=(",", ":")), encoding="utf-8"
            )
        except OSError as error:
            # A cache that cannot be written is slow, not broken.
            logger.warning("Could not write cache %s: %s", self.path, error)

    def _evict(self):
        if len(self.entries) <= MAX_ENTRIES:
            return

        def sort_key(number):
            try:
                return (1, int(number))
            except ValueError:
                return (0, 0)  # unparseable keys go first

        keep = sorted(self.entries, key=sort_key)[-MAX_ENTRIES:]
        self.entries = {number: self.entries[number] for number in keep}


def forget(cfg):
    """Drop the cache for one account, e.g. after signing in as someone else."""
    try:
        cache_path(cfg).unlink()
    except OSError:
        pass
