"""URL handling and error translation, with no network."""

import json

import pytest
import requests

from avogadro_webmo.client import (
    WebMOAuthError,
    WebMOClient,
    WebMOError,
    normalize_url,
)

ENDPOINT = "https://host.example/cgi-bin/webmo/rest.cgi"


@pytest.mark.parametrize(
    "pasted",
    [
        "https://host.example/cgi-bin/webmo/login.cgi",
        "https://host.example/cgi-bin/webmo/rest.cgi",
        "https://host.example/cgi-bin/webmo/",
        "https://host.example/cgi-bin/webmo",
        "https://host.example",
        "host.example",
    ],
)
def test_normalize_url_reaches_the_endpoint(pasted):
    assert normalize_url(pasted) == ENDPOINT


def test_normalize_url_handles_a_subdirectory_install():
    assert (
        normalize_url("https://www.webmo.net/demoserver")
        == "https://www.webmo.net/demoserver/cgi-bin/webmo/rest.cgi"
    )


def test_normalize_url_rejects_nothing_useful():
    with pytest.raises(WebMOError):
        normalize_url("   ")


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text if payload is None else json.dumps(payload)
        self.content = self.text.encode()

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, params=None, data=None, timeout=None):
        self.calls.append((method, url, params, data))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def client_with(response, token="tok"):
    client = WebMOClient(ENDPOINT, "guest", token)
    client._session = FakeSession(response)
    return client


def test_every_call_carries_the_token_and_user():
    client = client_with(FakeResponse(payload={"jobs": [3, 2, 1]}))
    assert client.jobs() == [3, 2, 1]
    _, url, params, _ = client._session.calls[0]
    assert url == ENDPOINT + "/jobs"
    assert params == {"token": "tok", "username": "guest"}


def test_filters_drop_empty_values():
    client = client_with(FakeResponse(payload={"jobs": []}))
    client.jobs(status="complete", engine="")
    _, _, params, _ = client._session.calls[0]
    assert params["status"] == "complete"
    assert "engine" not in params


def test_401_becomes_an_auth_error_carrying_the_server_text():
    response = FakeResponse(401, {"error": "Invalid username or password/token"})
    with pytest.raises(WebMOAuthError, match="Invalid username"):
        client_with(response).jobs()


def test_missing_token_is_an_auth_error_before_any_request():
    client = client_with(FakeResponse(payload={}), token=None)
    with pytest.raises(WebMOAuthError):
        client.jobs()
    assert client._session.calls == []


def test_an_html_error_page_is_not_mistaken_for_json():
    response = FakeResponse(200, None, "<html>Service Unavailable</html>")
    with pytest.raises(WebMOError, match="did not return JSON"):
        client_with(response).jobs()


def test_a_200_carrying_an_error_key_still_raises():
    with pytest.raises(WebMOError, match="No such job"):
        client_with(FakeResponse(payload={"error": "No such job"})).job(1)


def test_a_transport_failure_names_the_server():
    client = client_with(requests.ConnectionError("no route to host"))
    with pytest.raises(WebMOError, match="Could not reach"):
        client.jobs()


def test_status_needs_no_token():
    client = client_with(FakeResponse(payload={"version": "26.0"}), token=None)
    assert client.status()["version"] == "26.0"
    _, _, params, _ = client._session.calls[0]
    assert "token" not in params
