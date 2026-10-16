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

from unittest.mock import MagicMock, patch

import pytest
from werkzeug.exceptions import BadRequest

from superset.views.core import Superset


def test_language_pack_no_has_access_decorator():
    """Ensure language_pack does not require authentication/has_access."""
    # has_access decorator wraps functions and attaches permission attributes.
    # The language_pack function should be directly accessible.
    func = Superset.language_pack
    assert not hasattr(func, "_permission_name")


def test_language_pack_invalid_lang_code():
    view = Superset()
    with pytest.raises(BadRequest):
        view.language_pack("invalid/path")

    with pytest.raises(BadRequest):
        view.language_pack("zh_CN_extra")

    with pytest.raises(BadRequest):
        view.language_pack("../etc/passwd")

    # a trailing newline would pass a `re.match(...$)` anchor ("$" matches
    # before a trailing \n) but must be rejected by re.fullmatch
    with pytest.raises(BadRequest):
        view.language_pack("en\n")


def test_language_pack_not_found(app):
    with app.test_request_context():
        view = Superset()
        with patch("os.path.isfile", return_value=False):
            resp = view.language_pack("zz")
            assert resp.status_code == 404
            assert b"Language pack doesn't exist on the server" in resp.data


def test_language_pack_found(app):
    with app.test_request_context():
        view = Superset()
        with (
            patch("os.path.isfile", return_value=True),
            patch("superset.views.core.send_file") as mock_send_file,
        ):
            mock_send_file.return_value = MagicMock(status_code=200)
            resp = view.language_pack("zh")
            assert resp.status_code == 200
            mock_send_file.assert_called_once()
            (file_path,) = mock_send_file.call_args.args
            kwargs = mock_send_file.call_args.kwargs
            assert file_path.endswith("zh/LC_MESSAGES/messages.json")
            assert kwargs.get("mimetype") == "application/json"


def test_language_pack_anonymous_access_is_not_redirected(client):
    """Language pack must be reachable anonymously (no 302 to the login page)."""
    resp = client.get("/superset/language_pack/zz/")
    # A missing pack yields 404; if authentication were reintroduced on this
    # endpoint, Flask-AppBuilder would instead return a 302 login redirect.
    assert resp.status_code == 404
    # The view's own 404 body is JSON; a routing-level 404 would return HTML,
    # so this also guards against the route itself regressing/disappearing.
    assert b"Language pack doesn't exist on the server" in resp.data
