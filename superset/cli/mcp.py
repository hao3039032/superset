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
"""CLI module for MCP service"""

import click
from flask.cli import with_appcontext


@click.group()
def mcp() -> None:
    """Model Context Protocol service commands"""
    pass


@mcp.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=5008, help="Port to bind to")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def run(host: str, port: int, debug: bool) -> None:
    """Run the MCP service"""
    try:
        from superset.mcp_service.server import run_server

        run_server(host=host, port=port, debug=debug)
    except ImportError as e:
        click.echo(
            f"Error: MCP service dependencies not installed: {e}\n"
            "Please install with: pip install fastmcp",
            err=True,
        )
        raise click.ClickException("MCP service not available") from e


@mcp.command("issue-token")
@click.argument("identity")
@click.option(
    "--hours", type=click.IntRange(min=1), help="Validity in hours (default: 2160)"
)
@click.option(
    "--permanent", is_flag=True, help="Issue a token without an expiration time"
)
@with_appcontext
def issue_token(identity: str, hours: int | None, permanent: bool) -> None:
    """Issue an MCP token for an existing username or email address."""
    from superset.mcp_service.tokens import issue_token as sign_token

    if permanent and hours is not None:
        raise click.UsageError("Use either --hours or --permanent, not both")
    try:
        token = sign_token(identity, hours=None if permanent else hours or 2160)
    except ValueError as ex:
        raise click.ClickException(str(ex)) from ex
    click.echo(token)
