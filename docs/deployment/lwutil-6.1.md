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
Supply `BASE_IMAGE` as a local snapshot tag of the dependency-complete 6.1.0
MCP image, verify its image ID with `docker inspect`, and supply `VCS_REF` as
the full Git commit. Dockerfile FROM does not accept a bare image ID. The build replaces Python source
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

## Frontend changes

Backend-only patches keep the fast path above: the deploy-mcp image just
copies `superset/` over a frozen base, and the base still carries the official
6.1.0 frontend assets. Any change under `superset-frontend/` breaks that
assumption: the browser loads chart code from the Web image, so the frontend
must be rebuilt and Web (and any worker serving assets) must roll too.

The flow for a frontend change:

1. Build the base dev image from the repository root `Dockerfile` at the
   merged commit (its node:20 stage runs `npm ci` + `npm run build`). Target
   the `dev` stage explicitly — the default final stage is `showtime` (lean
   dependency set), while `docker/Dockerfile.deploy-lwutil` expects a `dev`
   base:
   `docker build --target dev -f Dockerfile -t superset-local:6.1-lw-fe1 .`
   Tag immutably (`-fe1`, `-fe2`, ...) per frontend batch; the build is large
   and slow, so batch frontend patches together.
2. Rebuild the Web/workers overlay on the new base:
   `docker build -f docker/Dockerfile.deploy-lwutil --build-arg BASE=superset-local:6.1-lw-fe1 -t <deploy-tag> .`
3. Rebuild the MCP image on the step-2 overlay image via
   `--build-arg BASE_IMAGE=<deploy-tag>` so both images share one patched
   source tree; verify the image ID with `docker inspect` as usual. The base
   must be dependency-complete: `docker/Dockerfile.deploy-mcp` only copies
   Python source and installs nothing, and the step-1 `dev` image lacks
   `clickhouse-connect` and `numexpr` and pins the dev-only `fastmcp` 3.1.0 —
   using it here would produce an MCP image whose ClickHouse charts fail to
   load their dialect.
4. Update `x-superset-image` for the Web/workers services in
   `docker-compose-image-tag.yml` and the MCP image reference, then recreate
   the affected services. Save the previous Compose file and image IDs first.
   This is the one case where the "Web, workers... retain their existing
   deployment" rule from the intro is intentionally broken; PostgreSQL and
   Redis still do not roll.
5. Smoke checks in addition to the backend list: a chart configured with
   `legend.selected` in its ECharts Options loads with the series hidden and
   can be re-selected by clicking the legend; charts without custom options
   render unchanged; a configured default `dataZoom` window opens as
   documented. Before rollout, also audit saved charts whose ECharts Options
   already contain `legend.selected`: those settings were silently dropped
   by the old schema and will start hiding series once this frontend ships —
   and any entries whose value is not a boolean (e.g. a string) now make the
   whole custom-options object invalid, silently dropping all other
   customizations; fix those values during the audit.
   Verify the chart bundle actually changed by checking the asset
   hash in the browser (a stale CDN/browser cache can mask a missing rollout).

After a frontend roll, subsequent backend-only patches go back to the fast
path, but their `BASE_IMAGE` default in `docker/Dockerfile.deploy-mcp` must be
advanced to the new verified snapshot tag so Python-only rebuilds stay
consistent with the deployed frontend.
