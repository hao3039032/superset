<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements. See the NOTICE file
for additional information regarding copyright ownership.
The ASF licenses this file to you under the Apache License, Version 2.0
(the "License"); you may not use this file except in compliance
with the License. You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
OF ANY KIND, either express or implied. See the License for details.
-->

# lwutil Superset 6.1 deployment branch

`deploy/6.1` is the maintained source branch for the lwutil MCP service.
Start each fix or feature branch from it, review through a PR, and deploy the
merged commit using an immutable image tag. Keep upstream tracking branches
separate. Web, workers, PostgreSQL and Redis retain their existing deployment
until a change requires updating them.

## Baseline and patch inventory

Initial baseline: `fix/6.1.0-mcp-followup` at
`e29c93df44dbd5c4332910268555bc7b6bd053bf` (Superset 6.1.0).
Inherited fixes: JWT user identity middleware, readable authentication and tool
errors, token CLI, instance metadata resource, namespaced `call_tool` dispatch.

Sankey: backport of apache/superset#43573, reviewed at upstream head
`eb72811b549c0972e93199093a3c20a1a803b960`.
The upstream plugin architecture is not present in this baseline, so the
backport uses its existing schema, validator and form-data mapping architecture.
It also handles native Sankey source/target columns during previews and chart
data retrieval. There are no database migrations or frontend changes.

Before upgrading Superset, check whether upstream has absorbed each fix and
reapply only the patches still needed. Do not merge upstream master wholesale
into this release branch.

## Sankey MCP configuration

Discover the schema with `get_chart_type_schema(chart_type="sankey_v2")`.
Pass this config to `generate_chart` with an accessible dataset ID:

```json
{
  "chart_type": "sankey_v2",
  "source": {"name": "from_stage"},
  "target": {"name": "to_stage"},
  "metric": {"name": "users", "aggregate": "SUM"},
  "sort_by_metric": true,
  "row_limit": 10000,
  "color_scheme": "supersetColors"
}
```

Use `saved_metric: true` with a dataset metric name instead of `aggregate`
for a saved metric. Structured `filters` are supported. Node references must
be dimensions. The available settings match the 6.1.0 Sankey control panel;
this backport does not add new frontend styling controls or raw SQL expressions.
Use `add_chart_to_existing_dashboard` to place the generated chart on a dashboard.

## Build and rollout

Build from the exact merged commit using `docker/Dockerfile.deploy-mcp`.
Supply `BASE_IMAGE` as the immutable ID of the dependency-complete 6.1.0 MCP
image and `VCS_REF` as the full Git commit. The build replaces Python source
without resolving or upgrading runtime dependencies; the existing image uses
editable installs under `/app` and retains the official frontend assets.

On lwutil, the existing Compose project is `superset_source`, its configuration
is `/var/lib/superset/superset_source/docker-compose-image-tag.yml`, and the
service to update is `superset-mcp`. Keep local environment files, signing keys,
configuration and volumes outside Git. Save the previous Compose file and image
ID before changing only the MCP image and recreating it with `--no-deps`.

Verify authenticated MCP initialization, schema discovery, chart creation/data
and dashboard placement; also check missing/invalid credentials remain rejected.
Check Web health and that the other containers have not restarted. For rollback,
restore the previous MCP image in Compose and recreate only `superset-mcp`.
No metadata downgrade is needed for this source-only backport.
