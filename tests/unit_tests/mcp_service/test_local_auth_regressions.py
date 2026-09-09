# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""JWT identity and local token issuance regressions."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from click.testing import CliRunner
from flask import current_app, g

from superset.cli.mcp import mcp
from superset.mcp_service.auth import get_user_from_request
from superset.mcp_service.tokens import issue_token


@pytest.mark.parametrize("subject", ["alice", "bob"])
def test_verified_subject_overrides_stale_identity(
    app_context: None, subject: str
) -> None:
    user = SimpleNamespace(username=subject, is_active=True)
    g.user = SimpleNamespace(username="stale-admin")
    with (
        patch.dict(current_app.config, MCP_AUTH_ENABLED=True),
        patch(
            "fastmcp.server.dependencies.get_access_token",
            return_value=SimpleNamespace(claims={"sub": subject}),
        ),
        patch(
            "superset.mcp_service.auth.load_user_with_relationships", return_value=user
        ) as loader,
    ):
        assert get_user_from_request() is user
        loader.assert_called_once_with(username=subject)


@pytest.mark.parametrize("claims", [None, {}, {"sub": ""}, {"sub": 1}])
def test_authenticated_mode_never_falls_back_to_dev_user(
    app_context: None, claims: dict[str, object] | None
) -> None:
    g.user = SimpleNamespace(username="admin")
    token = SimpleNamespace(claims=claims) if claims is not None else None
    with (
        patch.dict(current_app.config, MCP_AUTH_ENABLED=True, MCP_DEV_USERNAME="admin"),
        patch("fastmcp.server.dependencies.get_access_token", return_value=token),
        pytest.raises(ValueError, match="verified JWT"),
    ):
        get_user_from_request()


@pytest.mark.parametrize("user", [None, SimpleNamespace(is_active=False)])
def test_unknown_or_inactive_token_subject_denied(app_context: None, user: Any) -> None:
    with (
        patch.dict(current_app.config, MCP_AUTH_ENABLED=True),
        patch(
            "fastmcp.server.dependencies.get_access_token",
            return_value=SimpleNamespace(claims={"sub": "alice"}),
        ),
        patch(
            "superset.mcp_service.auth.load_user_with_relationships", return_value=user
        ),
        pytest.raises(ValueError, match="Unknown or inactive"),
    ):
        get_user_from_request()


@pytest.fixture
def signing_config(app_context: None) -> Iterator[None]:
    with patch.dict(
        current_app.config,
        MCP_AUTH_ENABLED=True,
        MCP_JWT_ALGORITHM="HS256",
        MCP_JWT_SECRET="test-only-key" * 4,
        MCP_JWT_ISSUER="test-issuer",
        MCP_JWT_AUDIENCE="test-audience",
    ):
        yield


@pytest.mark.parametrize("hours", [None, 8])
def test_token_uses_canonical_username_and_explicit_lifetime(
    signing_config: None, hours: int | None
) -> None:
    user = SimpleNamespace(username="alice", is_active=True)
    with patch("superset.mcp_service.tokens.security_manager", new=MagicMock()) as sm:
        sm.find_user.return_value = user
        encoded = issue_token("alice", hours)
    claims = jwt.decode(
        encoded,
        "test-only-key" * 4,
        algorithms=["HS256"],
        issuer="test-issuer",
        audience="test-audience",
    )
    assert claims["sub"] == "alice"
    assert claims["jti"]
    if hours is None:
        assert "exp" not in claims
    else:
        assert claims["exp"] - claims["iat"] == hours * 3600


def test_email_resolves_canonical_username(signing_config: None) -> None:
    user = SimpleNamespace(username="alice", is_active=True)
    with (
        patch("superset.mcp_service.tokens.security_manager", new=MagicMock()) as sm,
        patch("superset.mcp_service.tokens.db", new=MagicMock()) as database,
    ):
        sm.find_user.return_value = None
        database.session.query.return_value.filter.return_value.all.return_value = [
            user
        ]
        encoded = issue_token("Alice@Example.com", None)
    claims = jwt.decode(
        encoded, "test-only-key" * 4, algorithms=["HS256"], audience="test-audience"
    )
    assert claims["sub"] == "alice"


@pytest.mark.parametrize("matches", [[], [MagicMock(), MagicMock()]])
def test_unknown_or_ambiguous_email_is_not_signed(signing_config, matches) -> None:
    with (
        patch("superset.mcp_service.tokens.security_manager", new=MagicMock()) as sm,
        patch("superset.mcp_service.tokens.db", new=MagicMock()) as database,
    ):
        sm.find_user.return_value = None
        database.session.query.return_value.filter.return_value.all.return_value = (
            matches
        )
        with pytest.raises(ValueError, match="No account|Multiple accounts"):
            issue_token("alice@example.com", None)


def test_inactive_account_cannot_receive_token(signing_config: None) -> None:
    with patch("superset.mcp_service.tokens.security_manager", new=MagicMock()) as sm:
        sm.find_user.return_value = SimpleNamespace(is_active=False)
        with pytest.raises(ValueError, match="inactive"):
            issue_token("alice", None)


def test_cli_permanent_option(app_context: None) -> None:
    with patch(
        "superset.mcp_service.tokens.issue_token", return_value="signed-token"
    ) as sign:
        result = CliRunner().invoke(
            mcp, ["issue-token", "alice@example.com", "--permanent"]
        )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "signed-token"
    sign.assert_called_once_with("alice@example.com", hours=None)


def test_cli_rejects_conflicting_lifetimes(app_context: None) -> None:
    with patch("superset.mcp_service.tokens.issue_token") as sign:
        result = CliRunner().invoke(
            mcp, ["issue-token", "alice", "--permanent", "--hours", "8"]
        )
    assert result.exit_code != 0
    sign.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_requests_keep_distinct_flask_users(app_context: None) -> None:
    import asyncio
    from contextvars import ContextVar

    from superset.mcp_service.middleware import JWTUserContextMiddleware

    subject: ContextVar[str] = ContextVar("test_subject")
    app = current_app._get_current_object()
    g.user = SimpleNamespace(username="outer-user")

    async def invoke(username: str) -> str:
        subject.set(username)

        async def handler(context: Any) -> str:
            await asyncio.sleep(0)
            assert g.user.username == username
            return g.user.username

        return await JWTUserContextMiddleware().on_request(MagicMock(), handler)

    with (
        patch.dict(app.config, MCP_AUTH_ENABLED=True),
        patch(
            "fastmcp.server.dependencies.get_access_token",
            side_effect=lambda: SimpleNamespace(claims={"sub": subject.get()}),
        ),
        patch("superset.mcp_service.flask_singleton.get_flask_app", return_value=app),
        patch(
            "superset.mcp_service.auth.load_user_with_relationships",
            side_effect=lambda username: SimpleNamespace(
                username=username, is_active=True
            ),
        ),
    ):
        assert await asyncio.gather(invoke("alice"), invoke("bob")) == ["alice", "bob"]
    assert g.user.username == "outer-user"


@pytest.mark.asyncio
@pytest.mark.parametrize("permanent", [False, True])
async def test_real_signed_token_accepted_by_both_verifiers(permanent: bool) -> None:
    import time

    from fastmcp.server.auth.providers.jwt import JWTVerifier

    from superset.mcp_service.jwt_verifier import DetailedJWTVerifier

    secret = "test-only-signing-secret" * 3
    claims: dict[str, Any] = {"sub": "alice", "iss": "issuer", "aud": "audience"}
    if not permanent:
        claims["exp"] = int(time.time()) + 60
    encoded = jwt.encode(claims, secret, algorithm="HS256")
    for verifier_type in [JWTVerifier, DetailedJWTVerifier]:
        verifier = verifier_type(
            public_key=secret, algorithm="HS256", issuer="issuer", audience="audience"
        )
        verified = await verifier.verify_token(encoded)
        assert verified is not None
        assert verified.claims["sub"] == "alice"
        expired = jwt.encode({**claims, "exp": 0}, secret, algorithm="HS256")
        assert await verifier.verify_token(expired) is None
        forged = jwt.encode(claims, "another-signing-secret" * 3, algorithm="HS256")
        assert await verifier.verify_token(forged) is None
