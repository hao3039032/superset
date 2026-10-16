#!/bin/bash
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

# This script generates .mo binary files from .po translation files
# these .mo files are used by the backend to load translations
#
# pybabel is preferred because, like the historical `flask fab babel-compile`
# entrypoint, it includes fuzzy entries (-f) and still writes a .mo file for a
# catalog even when format checkers report errors on individual messages.

if command -v pybabel &> /dev/null; then
  echo "Compiling .po to .mo using pybabel (fuzzy entries included)..."
  # pybabel returns a non-zero exit code when format checkers report errors,
  # but the .mo files are still written for every catalog; surface the errors
  # without aborting so partially invalid catalogs still ship.
  if ! pybabel compile -f -d superset/translations; then
    echo "WARNING: pybabel reported format errors; .mo files were still written for the valid catalogs." >&2
  fi
  # Checker warnings leave .mo files behind, but a hard crash may not; verify
  # that at least the primary catalogs were produced before declaring success.
  for locale in zh en; do
    if [ ! -f "superset/translations/${locale}/LC_MESSAGES/messages.mo" ]; then
      echo "ERROR: pybabel did not produce superset/translations/${locale}/LC_MESSAGES/messages.mo" >&2
      exit 1
    fi
  done
  echo "Finished compiling .mo files with pybabel."
elif command -v msgfmt &> /dev/null; then
  echo "pybabel not found, falling back to msgfmt (fuzzy entries are included)..."
  failed=0
  for file in $(find superset/translations -name "*.po"); do
    mo_file="${file%.*}.mo"
    if ! msgfmt --use-fuzzy "$file" -o "$mo_file"; then
      echo "ERROR: failed to compile $file" >&2
      failed=1
    fi
  done
  if [ "$failed" -ne 0 ]; then
    echo "ERROR: one or more catalogs failed to compile; .mo files for them were NOT regenerated." >&2
    exit 1
  fi
  echo "Successfully compiled .mo files."
elif command -v flask &> /dev/null; then
  echo "Compiling using flask fab..."
  flask fab babel-compile --target superset/translations
else
  echo "Error: Neither pybabel, msgfmt nor flask is available in PATH."
  exit 1
fi
