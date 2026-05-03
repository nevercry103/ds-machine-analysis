"""JWT auth tests — token creation and validation."""

from __future__ import annotations

import pytest

from api.middleware.auth import (
    Role,
    create_token,
    decode_token,
    has_permission,
)


_TEST_SECRET = "test-secret-for-unit-tests"


def test_create_and_decode_token():
    token = create_token(Role.ENGINEER, secret=_TEST_SECRET)
    assert isinstance(token, str)
    assert len(token) > 20

    payload = decode_token(token, secret=_TEST_SECRET)
    assert payload["role"] == "engineer"
    assert payload["sub"] == "engineer"
    assert payload["iss"] == "ds-machine-analyzer"


def test_all_roles_produce_valid_tokens():
    for role in Role:
        token = create_token(role, secret=_TEST_SECRET)
        payload = decode_token(token, secret=_TEST_SECRET)
        assert payload["role"] == role.value


def test_invalid_secret_raises():
    from jose import JWTError

    token = create_token(Role.OPERATOR, secret=_TEST_SECRET)
    with pytest.raises(JWTError):
        decode_token(token, secret="wrong-secret")


def test_permissions_matrix():
    assert has_permission(Role.OPERATOR, "machine:read")
    assert has_permission(Role.OPERATOR, "downtime:tag")
    assert not has_permission(Role.OPERATOR, "machine:configure")

    assert has_permission(Role.ENGINEER, "machine:configure")
    assert has_permission(Role.ENGINEER, "cycle:replay")
    assert has_permission(Role.ENGINEER, "logbook:write")

    assert has_permission(Role.MANAGER, "report:export")
    assert not has_permission(Role.MANAGER, "plc:write")

    assert has_permission(Role.EXECUTIVE, "report:export")
    assert not has_permission(Role.EXECUTIVE, "alarm:ack")
