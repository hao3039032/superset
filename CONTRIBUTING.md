<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements.  See the NOTICE file
 distributed with this work for additional information
 regarding copyright ownership.  The ASF licenses this file
 to you under the Apache License, Version 2.0 (the
 "License"); you may not use this file except in compliance
 with the License.  You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing,
 software distributed under the License is distributed on an
 "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 KIND, either express or implied.  See the License for the
 specific language governing permissions and limitations
 under the License.
-->
# Contributing to Apache Superset

Contributions are welcome and are greatly appreciated! Every
little bit helps, and credit will always be given.

## Developer Portal

All developer and contribution documentation has moved to the Apache Superset Developer Portal:

**[📚 View the Developer Portal →](https://superset.apache.org/developer_portal/)**

The Developer Portal includes comprehensive guides for:
- [Contributing Overview](https://superset.apache.org/developer_portal/contributing/overview)
- [Development Setup](https://superset.apache.org/developer_portal/contributing/development-setup)
- [Submitting Pull Requests](https://superset.apache.org/developer_portal/contributing/submitting-pr)
- [Contribution Guidelines](https://superset.apache.org/developer_portal/contributing/guidelines)
- [Code Review Process](https://superset.apache.org/developer_portal/contributing/code-review)
- [Development How-tos](https://superset.apache.org/developer_portal/contributing/howtos)

Source for the Developer Portal documentation is [located here](https://github.com/apache/superset/tree/master/docs/developer_portal).

## Internationalization (i18n) & Localization

When adding or modifying user-facing text:
- Always wrap user-facing strings with `t(...)` in frontend (React/TypeScript) and `_("...")` in backend (Flask/Python).
- Avoid string concatenation with user-facing text; use parameterized strings (e.g. `t('Hello %s', name)`).
- Update and compile translations when adding new strings (all commands must run from the repository root, unless noted otherwise):
  - Prerequisites: `pybabel` (installed with the development requirements) and GNU gettext (`msgcat`/`msgfmt`; on macOS install via `brew install gettext`).
  - Extract and update catalogs: `./scripts/translations/babel_update.sh` — note this rewrites **all** locale `.po` files and produces a large diff; run it only when intentionally refreshing catalogs.
  - Compile backend catalogs: `./scripts/translations/generate_mo_files.sh`
  - Compile frontend JSON packs: `npm run build-translation` (inside `superset-frontend`)
