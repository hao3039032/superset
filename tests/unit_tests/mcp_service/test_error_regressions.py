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
"""Keep MCP errors actionable and distinguish successful SQL responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError, ValidationError as MCPValidationError
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

from superset.mcp_service.middleware import (
    GlobalErrorHandlerMiddleware,
    LoggingMiddleware,
    StructuredContentStripperMiddleware,
)


@pytest.mark.parametrize(
    ("payload", "failed"),
    [
        ('{"success":true,"error":null,"error_type":null,"rows":[{"value":1}]}', False),
        ('{"success":false,"error":"invalid SQL","error_type":"FAILED"}', True),
        ('{"error":"missing dataset"}', True),
        ('{"rows":[{"error_type":"data column, not an error"}]}', False),
        ("plain text", False),
    ],
)
def test_error_detection_uses_values_not_field_presence(
    payload: str, failed: bool
) -> None:
    result = ToolResult(content=[TextContent(type="text", text=payload)])
    assert LoggingMiddleware()._is_error_response(result) is failed


@pytest.mark.asyncio
async def test_transport_preserves_protocol_error_flag() -> None:
    middleware = StructuredContentStripperMiddleware()
    result = await middleware.on_call_tool(
        MagicMock(),
        AsyncMock(
            return_value=ToolResult(
                content=[TextContent(type="text", text="denied")],
                structured_content={"error": "denied"},
                is_error=True,
            )
        ),
    )
    assert result.is_error is True
    assert result.structured_content is None


@pytest.mark.asyncio
async def test_transport_marks_returned_error_schema() -> None:
    result = await StructuredContentStripperMiddleware().on_call_tool(
        MagicMock(),
        AsyncMock(
            return_value=ToolResult(
                content=[
                    TextContent(type="text", text='{"success":false,"error":"bad SQL"}')
                ],
            )
        ),
    )
    assert result.is_error is True


@pytest.mark.asyncio
async def test_fastmcp_validation_is_actionable_and_audited(app_context: None) -> None:
    ctx = MagicMock(method="tools/call")
    error = MCPValidationError("request.dataset_id: Field required")
    with patch("superset.mcp_service.middleware.event_logger") as events:
        with pytest.raises(ToolError, match="Validation error.*dataset_id"):
            await GlobalErrorHandlerMiddleware()._handle_error(
                error, ctx, "generate_chart", 3
            )
    fields = events.log.call_args.kwargs
    assert fields["dashboard_id"] is None
    assert fields["slice_id"] is None
    assert fields["referrer"] is None


@pytest.mark.asyncio
async def test_exception_is_not_returned_as_success() -> None:
    result = await StructuredContentStripperMiddleware().on_call_tool(
        MagicMock(),
        AsyncMock(side_effect=ToolError("request.dataset_id: Field required")),
    )
    assert result.is_error is True
    assert "dataset_id" in result.content[0].text
