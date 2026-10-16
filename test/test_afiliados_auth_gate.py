from unittest.mock import patch

import pytest

from app.controllers import base
from app.models.exception import HttpException


class FakeRequest:
    headers = {}

def test_missing_api_key_fails_closed():
    with patch.object(base.config, "app", {"api_key": ""}):
        with pytest.raises(HttpException) as exc:
            base.verify_token(FakeRequest())
        assert exc.value.status_code == 503

def test_wrong_api_key_rejected():
    with patch.object(base.config, "app", {"api_key": "expected-secret"}):
        with pytest.raises(HttpException) as exc:
            base.verify_token(FakeRequest())
        assert exc.value.status_code == 401
