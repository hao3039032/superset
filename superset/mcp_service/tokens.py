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
"""Issue locally managed JWT credentials for the MCP service."""

import secrets
import time
from typing import Any

import jwt
from flask import current_app
from sqlalchemy import func

from superset import db, security_manager


def issue_token(identity: str, hours: int | None = 2160) -> str:
    """Sign an active user's MCP token; None explicitly requests no expiry.

    An exact username takes precedence over a case-insensitive email match.
    The JWT subject always contains the canonical username used by MCP RBAC.
    """
    if hours is not None and hours <= 0:
        raise ValueError("Token validity must be a positive number of hours")
    config = current_app.config
    if not config.get("MCP_AUTH_ENABLED"):
        raise ValueError("MCP authentication must be enabled before issuing tokens")
    if config.get("MCP_JWT_ALGORITHM") != "HS256":
        raise ValueError("Local token issuance requires MCP_JWT_ALGORITHM=HS256")
    for key in ("MCP_JWT_SECRET", "MCP_JWT_ISSUER", "MCP_JWT_AUDIENCE"):
        if not config.get(key):
            raise ValueError(f"{key} must be configured")

    username = _resolve_username(identity)

    issued_at = int(time.time())
    claims: dict[str, Any] = {
        "sub": username,
        "iss": config["MCP_JWT_ISSUER"],
        "aud": config["MCP_JWT_AUDIENCE"],
        "iat": issued_at,
        "jti": secrets.token_urlsafe(24),
    }
    if hours is not None:
        claims["exp"] = issued_at + hours * 3600
    return jwt.encode(claims, config["MCP_JWT_SECRET"], algorithm="HS256")


def _resolve_username(identity: str) -> str:
    """Resolve an unambiguous, active account by username or email."""
    identity = identity.strip()
    user = security_manager.find_user(username=identity)
    if user is None:
        user_model = security_manager.user_model
        matches = (
            db.session.query(user_model)
            .filter(func.lower(user_model.email) == identity.lower())
            .all()
        )
        if len(matches) > 1:
            raise ValueError(
                "Multiple accounts share this email; use the exact username"
            )
        user = matches[0] if matches else None
    if user is None:
        raise ValueError("No account matches this username or email")
    if not user.is_active:
        raise ValueError("This Superset account is inactive")

    return user.username
