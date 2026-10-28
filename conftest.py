import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from locations.models import Category, Location
from users.models import User


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def factory(**kwargs):
        counter["n"] += 1
        n = counter["n"]
        kwargs.setdefault("username", f"user{n}")
        kwargs.setdefault("email", f"user{n}@example.com")
        password = kwargs.pop("password", "Str0ng-pass!")
        return User.objects.create_user(password=password, **kwargs)

    return factory


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def other_user(make_user):
    return make_user()


@pytest.fixture
def admin_user(make_user):
    return make_user(username="admin", is_staff=True)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def client_for():
    def factory(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    return factory


@pytest.fixture
def category(db):
    return Category.objects.create(name="Parks")


@pytest.fixture
def make_location(category):
    def factory(author, **kwargs):
        defaults = {
            "name": "Rynok Square",
            "description": "Historic central square",
            "category": category,
            "address": "Lviv",
            "latitude": "49.841952",
            "longitude": "24.031592",
        }
        defaults.update(kwargs)
        return Location.objects.create(author=author, **defaults)

    return factory


@pytest.fixture
def location(make_location, user):
    return make_location(user)
