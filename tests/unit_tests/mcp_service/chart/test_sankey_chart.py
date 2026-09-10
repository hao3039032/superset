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

"""Regression coverage for the 6.1 Sankey backport of apache/superset#43573."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from superset.mcp_service.chart.chart_utils import (
    _resolve_viz_type,
    generate_chart_name,
    map_config_to_form_data,
)
from superset.mcp_service.chart.preview_utils import _build_query_columns
from superset.mcp_service.chart.schemas import parse_chart_config, SankeyChartConfig
from superset.mcp_service.chart.tool.generate_chart import _compile_chart
from superset.mcp_service.chart.tool.get_chart_type_schema import (
    _get_chart_type_schema_impl,
)
from superset.mcp_service.chart.validation.dataset_validator import DatasetValidator
from superset.mcp_service.chart.validation.schema_validator import SchemaValidator
from superset.mcp_service.common.error_schemas import DatasetContext


@pytest.fixture
def sankey_config():
    return {
        "chart_type": "sankey_v2",
        "source": {"name": "origin"},
        "target": {"name": "destination"},
        "metric": {"name": "amount", "aggregate": "SUM"},
    }


@pytest.fixture
def dataset_context():
    return DatasetContext(
        id=1,
        table_name="flows",
        database_name="test",
        available_columns=[
            {"name": "Origin", "type": "VARCHAR", "is_numeric": False},
            {"name": "Destination", "type": "VARCHAR", "is_numeric": False},
            {"name": "Amount", "type": "FLOAT", "is_numeric": True},
        ],
        available_metrics=[{"name": "Total", "expression": "SUM(amount)"}],
    )


def test_schema_discovery_and_dispatch(sankey_config):
    info = _get_chart_type_schema_impl("sankey_v2")
    assert info["chart_type"] == "sankey_v2"
    for example in info["examples"]:
        assert isinstance(parse_chart_config(example), SankeyChartConfig)
    valid, error = SchemaValidator._pre_validate_chart_type("sankey_v2", sankey_config)
    assert valid
    assert error is None
    config = parse_chart_config(sankey_config)
    assert _resolve_viz_type(config) == "sankey_v2"
    assert "origin" in generate_chart_name(config)


@pytest.mark.parametrize("field", ["source", "target", "metric"])
def test_missing_required_fields(sankey_config, field):
    del sankey_config[field]
    valid, error = SchemaValidator._pre_validate_chart_type("sankey_v2", sankey_config)
    assert not valid
    assert field in error.message
    with pytest.raises(ValueError, match="Field required"):
        parse_chart_config(sankey_config)


@pytest.mark.parametrize("field", ["source", "target"])
@pytest.mark.parametrize("extra", [{"aggregate": "SUM"}, {"saved_metric": True}])
def test_nodes_cannot_be_metrics(sankey_config, field, extra):
    sankey_config[field].update(extra)
    with pytest.raises(ValidationError, match="plain node column"):
        SankeyChartConfig.model_validate(sankey_config)


@pytest.mark.parametrize(
    "extra", [{"row_limit": 0}, {"row_limit": 100001}, {"node_width": 20}]
)
def test_invalid_settings_are_not_silently_ignored(sankey_config, extra):
    with pytest.raises(ValidationError):
        SankeyChartConfig.model_validate({**sankey_config, **extra})


def test_metric_requires_aggregation(sankey_config):
    sankey_config["metric"].pop("aggregate")
    with pytest.raises(ValidationError, match="aggregate or saved_metric"):
        SankeyChartConfig.model_validate(sankey_config)


@pytest.mark.parametrize("sort", [True, False])
@pytest.mark.parametrize("saved", [True, False])
def test_query_contract_and_frontend_settings(sankey_config, sort, saved):
    if saved:
        sankey_config["metric"] = {"name": "total", "saved_metric": True}
    config = SankeyChartConfig.model_validate(
        {
            **sankey_config,
            "sort_by_metric": sort,
            "row_limit": 30,
            "color_scheme": "googleCategory10c",
            "filters": [{"column": "origin", "op": "=", "value": "A"}],
        }
    )
    form = map_config_to_form_data(config)
    assert form["source"] == "origin"
    assert form["target"] == "destination"
    assert form["groupby"] == ["origin", "destination"]
    assert form["row_limit"] == 30
    assert form["color_scheme"] == "googleCategory10c"
    assert form["adhoc_filters"][0]["subject"] == "origin"
    metric = form["metric"]
    assert metric == "total" if saved else metric["aggregate"] == "SUM"
    expected = ([[metric, False]] if sort else []) + [
        ["origin", True],
        ["destination", True],
    ]
    assert form["orderby"] == expected


def test_dataset_validation_normalization_and_saved_metrics(
    sankey_config, dataset_context
):
    config = SankeyChartConfig.model_validate(sankey_config)
    assert DatasetValidator.validate_against_dataset(config, 1, dataset_context)[0]
    normalized = DatasetValidator.normalize_column_names(config, 1, dataset_context)
    assert normalized.source.name == "Origin"
    assert normalized.target.name == "Destination"
    assert normalized.metric.name == "Amount"
    sankey_config["metric"] = {"name": "total", "saved_metric": True}
    config = SankeyChartConfig.model_validate(sankey_config)
    assert DatasetValidator.validate_against_dataset(config, 1, dataset_context)[0]
    assert (
        DatasetValidator.normalize_column_names(config, 1, dataset_context).metric.name
        == "Total"
    )
    sankey_config["source"]["name"] = "missing_column"
    config = SankeyChartConfig.model_validate(sankey_config)
    assert not DatasetValidator.validate_against_dataset(config, 1, dataset_context)[0]


def test_native_form_data_compiles_with_both_nodes(sankey_config):
    form = map_config_to_form_data(SankeyChartConfig.model_validate(sankey_config))
    form.pop("groupby")  # Native Explore saves source/target without groupby.
    assert _build_query_columns(form) == ["origin", "destination"]
    with (
        patch("superset.common.query_context_factory.QueryContextFactory") as factory,
        patch(
            "superset.commands.chart.data.get_data_command.ChartDataCommand"
        ) as command,
    ):
        command.return_value.run.return_value = {
            "queries": [
                {"data": [{"origin": "A", "destination": "B", "SUM(amount)": 3}]}
            ]
        }
        result = _compile_chart(form, 1)
        assert result.success
        query = factory.return_value.create.call_args.kwargs["queries"][0]
        assert query["columns"] == ["origin", "destination"]
        assert query["metrics"] == [form["metric"]]
        assert query["orderby"] == form["orderby"]
        command.return_value.validate.assert_called_once()
