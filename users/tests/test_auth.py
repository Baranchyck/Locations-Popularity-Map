import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"
LOGOUT = "/api/auth/logout/"
ME = "/api/auth/me/"
CSRF = "/api/auth/csrf/"
RESET = "/api/auth/password-reset/"
RESET_CONFIRM = "/api/auth/password-reset/confirm/"


@pytest.fixture
def csrf_client():
    return APIClient(enforce_csrf_checks=True)


def csrf_token(client):
    return client.get(CSRF).json()["csrfToken"]


def test_register_logs_in_and_normalizes_email(csrf_client):
    token = csrf_token(csrf_client)
    response = csrf_client.post(
        REGISTER,
        {"username": "bob", "email": "Bob@Example.com", "password": "Str0ng-pass!"},
        HTTP_X_CSRFTOKEN=token,
    )

    assert response.status_code == 201
    assert response.json()["email"] == "bob@example.com"
    assert "password" not in response.json()
    assert csrf_client.get(ME).json()["username"] == "bob"


def test_login_requires_csrf_token(csrf_client, user):
    response = csrf_client.post(LOGIN, {"username": user.username, "password": "Str0ng-pass!"})
    assert response.status_code == 403


def test_login_logout_flow(api_client, user):
    bad = api_client.post(LOGIN, {"username": user.username, "password": "wrong"})
    assert bad.status_code == 400

    ok = api_client.post(LOGIN, {"username": user.username, "password": "Str0ng-pass!"})
    assert ok.status_code == 200
    assert api_client.get(ME).status_code == 200

    assert api_client.post(LOGOUT).status_code == 204
    assert api_client.get(ME).status_code == 403


def test_password_reset_full_flow(api_client, user):
    response = api_client.post(RESET, {"email": user.email.upper()})
    assert response.status_code == 200
    assert len(mail.outbox) == 1

    body = mail.outbox[0].body
    uid = re.search(r"uid: (\S+)", body).group(1)
    token = re.search(r"token: (\S+)", body).group(1)

    assert api_client.get(RESET_CONFIRM, {"uid": uid, "token": token}).status_code == 200

    confirm = api_client.post(
        RESET_CONFIRM, {"uid": uid, "token": token, "new_password": "N3w-Str0ng-pass!"}
    )
    assert confirm.status_code == 200

    user.refresh_from_db()
    assert user.check_password("N3w-Str0ng-pass!")

    reuse = api_client.post(
        RESET_CONFIRM, {"uid": uid, "token": token, "new_password": "Another-pass-123!"}
    )
    assert reuse.status_code == 400


def test_password_reset_does_not_reveal_unknown_email(api_client):
    response = api_client.post(RESET, {"email": "nobody@example.com"})
    assert response.status_code == 200
    assert mail.outbox == []
