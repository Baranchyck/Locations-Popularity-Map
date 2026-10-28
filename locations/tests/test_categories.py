import pytest

pytestmark = pytest.mark.django_db

URL = "/api/categories/"


def test_only_admin_can_create_category(client_for, user, admin_user):
    assert client_for(user).post(URL, {"name": "Museums"}).status_code == 403
    assert client_for(admin_user).post(URL, {"name": "Museums"}).status_code == 201


def test_category_name_is_case_insensitively_unique(client_for, admin_user, category):
    response = client_for(admin_user).post(URL, {"name": category.name.upper()})
    assert response.status_code == 400


def test_category_in_use_cannot_be_deleted(client_for, admin_user, location):
    response = client_for(admin_user).delete(f"{URL}{location.category_id}/")
    assert response.status_code == 409
