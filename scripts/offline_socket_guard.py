"""Block non-loopback socket access for an offline demo process."""
from __future__ import annotations

import ipaddress
import socket


def _is_loopback_host(host: object) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    value = str(host).strip().lower().rstrip(".")
    if value in {"localhost", "ip6-localhost"}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _address_host(address: object) -> object:
    if isinstance(address, tuple) and address:
        return address[0]
    return None if isinstance(address, str) else address


def _assert_local(address: object) -> None:
    host = _address_host(address)
    if not _is_loopback_host(host):
        raise OSError(f"offline demo blocked non-loopback network address: {host}")


_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_getaddrinfo = socket.getaddrinfo


def _guarded_connect(self: socket.socket, address: object):
    _assert_local(address)
    return _original_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: object):
    _assert_local(address)
    return _original_connect_ex(self, address)


def _guarded_getaddrinfo(host: object, *args: object, **kwargs: object):
    if not _is_loopback_host(host):
        raise OSError(f"offline demo blocked DNS lookup: {host}")
    return _original_getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _guarded_connect
socket.socket.connect_ex = _guarded_connect_ex
socket.getaddrinfo = _guarded_getaddrinfo
