import pytest


@pytest.fixture(autouse=True)
def _fast_hasher(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
