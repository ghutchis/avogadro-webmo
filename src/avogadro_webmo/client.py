#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""A small synchronous client for the WebMO REST/JSON interface.

Deliberately not the `webmo` PyPI package: that one prompts with getpass() when
no password is passed, sends DELETE /sessions from __del__, offers no timeout
control, and its get_folders() expects a list where the server returns a dict.
None of that survives contact with a 30 s subprocess budget.
"""

import urllib.parse

import requests

# (connect, read). --user-options is killed at 30 s, so no single call may sit
# anywhere near that.
DEFAULT_TIMEOUT = (5.0, 15.0)


class WebMOError(RuntimeError):
    """The server, or the transport, refused."""


class WebMOAuthError(WebMOError):
    """Credentials or session token rejected; a fresh login is needed."""


def normalize_url(url):
    """Turn whatever the user pasted into the rest.cgi endpoint.

    Accepts the login page, the cgi-bin directory, a bare host, or the
    endpoint itself; the last case is a no-op, so this is idempotent.
    """
    url = (url or "").strip()
    if not url:
        raise WebMOError("No server URL set.")
    if "://" not in url:
        url = "https://" + url

    parsed = urllib.parse.urlsplit(url)
    if not parsed.netloc:
        raise WebMOError(f"{url!r} is not a URL.")

    path = parsed.path.rstrip("/")
    tail = path.rsplit("/", 1)[-1]
    if tail.endswith(".cgi"):
        # ".../login.cgi" and ".../rest.cgi" both land on rest.cgi
        path = path[: len(path) - len(tail)] + "rest.cgi"
    elif path.endswith("/cgi-bin/webmo"):
        path += "/rest.cgi"
    else:
        path += "/cgi-bin/webmo/rest.cgi"

    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class WebMOClient:
    """Every call carries token+username as query parameters, as WebMO wants."""

    def __init__(self, url, username, token=None, timeout=DEFAULT_TIMEOUT):
        self.url = normalize_url(url)
        self.username = username
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()

    # -- transport ----------------------------------------------------------

    def _json(self, method, path, *, auth=True, params=None, data=None):
        params = dict(params or {})
        if auth:
            if not self.token:
                raise WebMOAuthError("Not logged in to WebMO.")
            params.update(token=self.token, username=self.username)

        try:
            response = self._session.request(
                method,
                self.url + path,
                params=params,
                data=data,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise WebMOError(f"Could not reach {self.url}: {error}") from error

        if response.status_code in (401, 403):
            raise WebMOAuthError(_server_error(response) or "Not authorized.")
        if not response.ok:
            detail = _server_error(response) or f"HTTP {response.status_code}"
            raise WebMOError(f"{method} {path} failed: {detail}")

        try:
            payload = response.json()
        except ValueError as error:
            # A misconfigured server answers 200 with an HTML error page.
            raise WebMOError(
                f"{path} did not return JSON: {response.text[:200]!r}"
            ) from error
        if isinstance(payload, dict) and payload.get("error"):
            raise WebMOError(str(payload["error"]))
        return payload

    # -- sessions -----------------------------------------------------------

    def status(self):
        """Server version and job count. The one call needing no token."""
        return self._json("GET", "/status", auth=False)

    def login(self, password, hours=24):
        """There is deliberately no logout: the token is meant to outlive the
        process, and a destructor firing DELETE /sessions is exactly the
        misfeature that rules out the `webmo` package."""
        payload = self._json(
            "POST",
            "/sessions",
            auth=False,
            data={
                "username": self.username,
                "password": password,
                "expiration": hours,
            },
        )
        self.token = payload["token"]
        return self.token


    # -- jobs ---------------------------------------------------------------

    def jobs(self, **filters):
        """Job *numbers* only, newest first. The server caps this at 250."""
        params = {key: value for key, value in filters.items() if value}
        return self._json("GET", "/jobs", params=params)["jobs"]

    def job(self, number):
        """The metadata block: jobName, jobDescription, jobEngine, jobDate..."""
        return self._json("GET", f"/jobs/{number}")["properties"]

    def results(self, number):
        """QC_JSON, which Avogadro's qcschema reader parses directly."""
        return self._json("GET", f"/jobs/{number}/results")



def _server_error(response):
    """WebMO reports failures as {"error": "..."} even on a 401."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        return payload.get("error")
    return None
