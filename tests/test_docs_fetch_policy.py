from __future__ import annotations

import ipaddress

import pytest

from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError


PUBLIC = ipaddress.ip_address("93.184.216.34")


def _resolver(*answers: str):
    resolved = tuple(ipaddress.ip_address(value) for value in answers)
    return lambda _host: resolved



















