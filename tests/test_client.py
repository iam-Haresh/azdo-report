from __future__ import annotations

import base64
import io
import logging

import httpx
import pytest
import respx

from azdo_analyzer.client import AzdoClient, AzdoHttpError, ReadOnlyViolation, RedactingFilter

BASE = "https://azdo.example.local/DefaultCollection"
PAT = "s3cr3tPATvalue1234567890abcdefghijklmnop"


def make_client(**kw) -> AzdoClient:
    return AzdoClient(BASE, PAT, api_version="7.0", sleep=lambda _s: None, **kw)


def test_only_get_is_allowed():
    client = make_client()
    with pytest.raises(ReadOnlyViolation):
        client.request("POST", f"{BASE}/_apis/projects")
    with pytest.raises(ReadOnlyViolation):
        client._http.post(f"{BASE}/_apis/projects")  # the httpx hook blocks direct use too
    with pytest.raises(ReadOnlyViolation):
        client._http.delete(f"{BASE}/_apis/projects/x")


@respx.mock
def test_basic_auth_header_and_url_building():
    route = respx.get(f"{BASE}/Contoso%20Retail/_apis/git/repositories").mock(return_value=httpx.Response(200, json={"value": [{"id": "1"}]}))
    repos = make_client().get_list("git/repositories", project="Contoso Retail")
    assert repos == [{"id": "1"}]
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Basic " + base64.b64encode(f":{PAT}".encode()).decode()
    assert request.url.params["api-version"] == "7.0"


@respx.mock
def test_continuation_token_paging():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        if "continuationToken" not in request.url.params:
            return httpx.Response(200, json={"value": [{"id": 1}, {"id": 2}]}, headers={"x-ms-continuationtoken": "t1"})
        return httpx.Response(200, json={"value": [{"id": 3}]})

    respx.get(f"{BASE}/_apis/projects").mock(side_effect=handler)
    items = list(make_client().paged("projects", {"$top": 2}))
    assert [i["id"] for i in items] == [1, 2, 3]
    assert calls[1]["continuationToken"] == "t1"


@respx.mock
def test_skip_paging():
    def handler(request: httpx.Request) -> httpx.Response:
        skip = int(request.url.params["$skip"])
        return httpx.Response(200, json={"value": [{"n": skip + i} for i in range(2 if skip == 0 else 1)]})

    respx.get(f"{BASE}/P/_apis/git/repositories/r/pullrequests").mock(side_effect=handler)
    items = list(make_client().paged("git/repositories/r/pullrequests", project="P", mode="skip", page_size=2))
    assert [i["n"] for i in items] == [0, 1, 2]


@respx.mock
def test_retry_on_429_honours_retry_after():
    sleeps = []
    route = respx.get(f"{BASE}/_apis/projects").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "3"}),
        httpx.Response(503),
        httpx.Response(200, json={"value": []}),
    ])
    client = AzdoClient(BASE, PAT, sleep=sleeps.append)
    assert client.get_list("projects") == []
    assert route.call_count == 3
    assert sleeps[0] == 3.0


@respx.mock
def test_preview_version_fallback_is_remembered():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        version = request.url.params["api-version"]
        seen.append(version)
        if not version.endswith("-preview"):
            return httpx.Response(400, json={"typeKey": "VssInvalidPreviewVersionException",
                                             "message": "The -preview flag must be supplied in the api-version for such requests."})
        return httpx.Response(200, json={"value": [{"id": 1}]})

    respx.get(url__regex=rf"{BASE}/P/_apis/distributedtask/securefiles.*").mock(side_effect=handler)
    client = make_client()
    assert client.get_list("distributedtask/securefiles", project="P") == [{"id": 1}]
    assert client.get_list("distributedtask/securefiles", project="P") == [{"id": 1}]
    assert seen == ["7.0", "7.0-preview", "7.0-preview"]


@respx.mock
def test_errors_are_redacted_and_typed():
    respx.get(f"{BASE}/_apis/projects").mock(return_value=httpx.Response(401, json={"message": f"bad token {PAT}"}))
    with pytest.raises(AzdoHttpError) as info:
        make_client().get("projects")
    assert info.value.status == 401
    assert PAT not in str(info.value)


@respx.mock
def test_html_sign_in_page_means_auth_failure():
    respx.get(f"{BASE}/_apis/projects").mock(return_value=httpx.Response(203, text="<html>sign in</html>", headers={"content-type": "text/html"}))
    with pytest.raises(AzdoHttpError) as info:
        make_client().get("projects")
    assert info.value.status == 401


@respx.mock
def test_detect_api_version_steps_down():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["api-version"] == "7.1":
            return httpx.Response(400, json={"typeKey": "VssVersionOutOfRangeException",
                                             "message": "The requested REST API version of 7.1 is out of range for this server."})
        return httpx.Response(200, json={"value": []})

    respx.get(f"{BASE}/_apis/projects").mock(side_effect=handler)
    assert make_client().detect_api_version() == "7.0"


def test_logging_filter_redacts_pat_and_base64():
    client = make_client()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter(client.redact))
    logger = logging.getLogger("azdo_analyzer.test_redaction")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    token = base64.b64encode(f":{PAT}".encode()).decode()
    logger.info("pat=%s header=Basic %s", PAT, token)
    output = stream.getvalue()
    assert PAT not in output and token not in output
    assert "***" in output
