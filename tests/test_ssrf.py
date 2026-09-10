"""SSRF defences: scheme allowlist, private-IP rejection, redirect validation,
response limits and image-type detection."""
import asyncio
import ipaddress
import socket

import httpx
import pytest
from helpers import PNG_BYTES, SVG_BYTES

from services import _fetch_limited, assert_public_http_url, fetch_favicon, is_private_ip

PUBLIC_IP = "93.184.216.34"


def run(coro):
    return asyncio.run(coro)


def _patch_dns(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        try:
            ipaddress.ip_address(host)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port or 0))]
        except ValueError:
            pass
        if host == "private.test":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port or 0))]
        if host == "loopback.test":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port or 0))]
        if host == "unresolvable.test":
            raise socket.gaierror("Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


def test_assert_public_url_rejects_bad_schemes_and_hosts(data_paths, monkeypatch):
    _patch_dns(monkeypatch)
    for url in ["file:///etc/passwd", "javascript:alert(1)", "gopher://example.com/", "ftp://example.com/x"]:
        with pytest.raises(ValueError):
            assert_public_http_url(url)
    for url in ["http://127.0.0.1/", "http://[::1]/", "http://private.test/", "http://unresolvable.test/"]:
        with pytest.raises(ValueError):
            assert_public_http_url(url)
    assert_public_http_url(f"http://{PUBLIC_IP}/")


def test_is_private_ip_is_fail_closed(monkeypatch):
    _patch_dns(monkeypatch)
    assert is_private_ip("private.test") is True
    assert is_private_ip("loopback.test") is True
    assert is_private_ip("unresolvable.test") is True
    assert is_private_ip("") is True
    assert is_private_ip("public.test") is False


def test_fetch_favicon_rejects_private_page_before_any_request(data_paths):
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, content=PNG_BYTES)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    result = run(fetch_favicon("http://127.0.0.1:8000/", client=client))
    run(client.aclose())

    assert result is None
    assert requested == []


def test_fetch_favicon_rejects_redirect_to_private_address(data_paths):
    requested = []

    def handler(request):
        requested.append(str(request.url))
        if str(request.url) == f"http://{PUBLIC_IP}/page":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, content=PNG_BYTES)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    result = run(fetch_favicon(f"http://{PUBLIC_IP}/page", client=client))
    run(client.aclose())

    assert result is None
    assert "http://127.0.0.1/secret" not in requested


def test_fetch_favicon_skips_private_icon_and_uses_fallback(data_paths):
    requested = []

    def handler(request):
        url = str(request.url)
        requested.append(url)
        if url == f"http://{PUBLIC_IP}/page":
            return httpx.Response(200, content=b'<html><link rel="icon" href="http://127.0.0.1/icon.png"></html>')
        if url == f"http://{PUBLIC_IP}/favicon.ico":
            return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})
        return httpx.Response(200, content=PNG_BYTES)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    result = run(fetch_favicon(f"http://{PUBLIC_IP}/page", client=client))
    run(client.aclose())

    assert result is not None
    assert (data_paths["uploads"] / result).exists()
    assert "http://127.0.0.1/icon.png" not in requested


def test_fetch_favicon_skips_oversized_icon(data_paths):
    def handler(request):
        url = str(request.url)
        if url == f"http://{PUBLIC_IP}/page":
            return httpx.Response(200, content=f'<link rel="icon" href="http://{PUBLIC_IP}/big.png">'.encode())
        if url == f"http://{PUBLIC_IP}/big.png":
            return httpx.Response(200, content=PNG_BYTES, headers={"content-length": str(50 * 1024 * 1024)})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    result = run(fetch_favicon(f"http://{PUBLIC_IP}/page", client=client))
    run(client.aclose())
    assert result is None


def test_fetch_favicon_skips_svg_content(data_paths):
    def handler(request):
        url = str(request.url)
        if url == f"http://{PUBLIC_IP}/page":
            return httpx.Response(200, content=f'<link rel="icon" href="http://{PUBLIC_IP}/icon.svg">'.encode())
        if url.endswith("icon.svg"):
            return httpx.Response(200, content=SVG_BYTES, headers={"content-type": "image/svg+xml"})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    result = run(fetch_favicon(f"http://{PUBLIC_IP}/page", client=client))
    run(client.aclose())
    assert result is None


def test_fetch_favicon_saves_valid_icon(data_paths, monkeypatch):
    _patch_dns(monkeypatch)

    def handler(request):
        url = str(request.url)
        if url == "http://public.test/page":
            return httpx.Response(200, content=b'<link rel="icon" href="/icon.png">')
        if url == "http://public.test/icon.png":
            return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    result = run(fetch_favicon("http://public.test/page", client=client))
    run(client.aclose())

    assert result is not None
    assert result.endswith(".png")
    assert (data_paths["uploads"] / result).read_bytes() == PNG_BYTES


def test_fetch_limited_aborts_oversized_stream(data_paths):
    async def chunks():
        yield PNG_BYTES
        yield b"x" * 1024

    async def scenario():
        def handler(request):
            return httpx.Response(200, content=chunks())

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await _fetch_limited(client, f"http://{PUBLIC_IP}/stream", max_bytes=64, headers={})
        finally:
            await client.aclose()

    assert run(scenario()) is None
