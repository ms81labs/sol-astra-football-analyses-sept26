"""Local HTTP boundaries shared by the legacy review tools."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
import ipaddress
import json
import os
from pathlib import Path
import stat
from typing import Any


class HttpRequestError(ValueError):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


def loopback_host(value: str) -> str:
    if value.lower() == "localhost":
        return "127.0.0.1"
    try:
        if ipaddress.ip_address(value).is_loopback:
            return value
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("review servers require a loopback bind address")


def read_regular_file(path: Path) -> bytes:
    path = path.absolute()
    if ".." in path.parts:
        raise FileNotFoundError(path)
    parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise FileNotFoundError(path)
            return handle.read()
    except OSError:
        raise FileNotFoundError(path) from None
    finally:
        os.close(parent)


def read_json_payload(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    hosts = handler.headers.get_all("Host", [])
    port = handler.server.server_port
    address = handler.server.server_address[0]
    authority = f"[{address}]:{port}" if ":" in address else f"{address}:{port}"
    local_hosts = {authority, f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}"}
    if port == 80:
        local_hosts |= {host.removesuffix(":80") for host in local_hosts}
    if len(hosts) != 1 or hosts[0].lower() not in local_hosts:
        raise HttpRequestError("foreign_host", HTTPStatus.FORBIDDEN)
    origins = handler.headers.get_all("Origin", [])
    allowed_origins = {f"http://{hosts[0].lower()}"}
    if port == 80:
        origin = f"http://{hosts[0].lower().removesuffix(':80')}"
        allowed_origins = {origin, f"{origin}:80"}
    if origins and (len(origins) != 1 or origins[0].lower() not in allowed_origins):
        raise HttpRequestError("foreign_origin", HTTPStatus.FORBIDDEN)
    lengths = handler.headers.get_all("Content-Length", [])
    if handler.headers.get_all("Transfer-Encoding") or len(lengths) > 1:
        raise HttpRequestError("ambiguous_body_framing")
    if not lengths:
        raise HttpRequestError("content_length_required", HTTPStatus.LENGTH_REQUIRED)
    if not lengths[0].isascii() or not lengths[0].isdigit():
        raise HttpRequestError("invalid_content_length")
    try:
        length = int(lengths[0])
    except ValueError:
        raise HttpRequestError("invalid_content_length") from None
    if length > 65536:
        raise HttpRequestError("json_body_too_large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    if length == 0:
        raise HttpRequestError("json_body_required")
    try:
        raw = handler.rfile.read(length)
    except TimeoutError:
        raise HttpRequestError("body_read_timeout", HTTPStatus.REQUEST_TIMEOUT) from None
    if len(raw) != length:
        raise HttpRequestError("incomplete_json_body")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HttpRequestError("invalid_json_body") from None
    if not isinstance(payload, dict):
        raise HttpRequestError("json_body_must_be_object")
    return payload
