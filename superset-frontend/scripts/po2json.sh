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


# This script generates .json files from .po translation files
# these json files are used by the frontend to load translations

set -e

export NODE_NO_WARNINGS=1

PO2JSON_CMD="po2json"
if ! command -v po2json &> /dev/null; then
  PO2JSON_CMD="npx --yes po2json@0.4.5"
fi

PRETTIER_CMD="prettier"
if ! command -v prettier &> /dev/null; then
  PRETTIER_CMD="npx --yes prettier@3.8.1"
fi

for file in $( find ../superset/translations/** -name '*.po' );
do
  extension=${file##*.}
  filename="${file%.*}"
  if [ $extension == "po" ]
  then
    echo "Converting $file -> $filename.json"
    # --fallback-to-msgid keeps untranslated entries usable by falling back to
    # the English source string instead of emitting an empty translation.
    $PO2JSON_CMD --domain superset --format jed1.x --fuzzy --fallback-to-msgid $file $filename.json
    $PRETTIER_CMD --write $filename.json
  fi
done
