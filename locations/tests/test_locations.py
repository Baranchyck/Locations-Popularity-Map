import math
from datetime import timedelta

import pytest
from django.utils import timezone

from locations.models import Location, LocationView, Review

pytestmark = pytest.mark.django_db

URL = "/api/locations/"


def detail(location):
    return f"{URL}{location.pk}/"


def payload(category, **overrides):
    data = {
        "name": "High Castle",
        "description": "Viewpoint over the city",
        "category": category.pk,
        "address": "Lviv",
        "latitude": "49.848500",
        "longitude": "24.039300",
    }
    data.update(overrides)
    return data


def test_anonymous_can_read_but_not_create(api_client, location, category):
    assert api_client.get(URL).status_code == 200
    assert api_client.post(URL, payload(category)).status_code == 403


def test_create_sets_author_from_session(client_for, user, category):
    response = client_for(user).post(URL, payload(category))

    assert response.status_code == 201
    body = response.json()
    assert body["author"]["id"] == user.pk
    assert body["rating"] is None and body["reviews_count"] == 0


def test_only_author_or_admin_can_edit(client_for, location, other_user, admin_user):
    assert client_for(other_user).patch(detail(location), {"name": "X"}).status_code == 403
    assert client_for(admin_user).patch(detail(location), {"name": "By admin"}).status_code == 200


def test_delete_is_soft(client_for, api_client, location):
    assert client_for(location.author).delete(detail(location)).status_code == 204

    assert api_client.get(detail(location)).status_code == 404
    assert api_client.get(URL).json()["count"] == 0
    assert Location.all_objects.get(pk=location.pk).is_deleted is True


def test_stats_are_not_inflated_by_joins(api_client, location, make_user):
    Review.objects.create(location=location, author=make_user(), rating=5, text="a")
    Review.objects.create(location=location, author=make_user(), rating=3, text="b")
    LocationView.objects.bulk_create([LocationView(location=location) for _ in range(3)])

    body = api_client.get(URL).json()["results"][0]

    assert body["rating"] == 4.0
    assert body["reviews_count"] == 2
    assert body["views_7d"] == 3
    expected = 4.0 * math.log(1 + 2) + 0.5 * math.log(1 + 3)
    assert body["popularity"] == pytest.approx(expected, abs=1e-3)


def test_views_older_than_7_days_are_ignored(api_client, location):
    LocationView.objects.bulk_create([LocationView(location=location) for _ in range(2)])
    old = LocationView.objects.create(location=location)
    LocationView.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=8))

    assert api_client.get(URL).json()["results"][0]["views_7d"] == 2


def test_view_counted_once_per_hour_per_user(client_for, user, location):
    client = client_for(user)
    assert client.get(detail(location)).json()["views_7d"] == 1
    assert client.get(detail(location)).json()["views_7d"] == 1
    assert LocationView.objects.filter(location=location).count() == 1


@pytest.fixture
def rated_locations(make_location, user, make_user, category):
    top = make_location(user, name="Top", description="best coffee")
    mid = make_location(user, name="Mid", description="ok")
    unrated = make_location(make_user(), name="Unrated", description="new")
    Review.objects.create(location=top, author=make_user(), rating=5, text="!")
    Review.objects.create(location=mid, author=make_user(), rating=3, text="~")
    return top, mid, unrated


def ids(response):
    return [item["id"] for item in response.json()["results"]]


def test_search_by_name_and_description(api_client, rated_locations):
    top, *_ = rated_locations
    assert ids(api_client.get(URL, {"search": "coffee"})) == [top.pk]
    assert ids(api_client.get(URL, {"search": "TOP"})) == [top.pk]


def test_filter_by_rating_author_category(api_client, rated_locations, user, category):
    top, mid, unrated = rated_locations
    assert ids(api_client.get(URL, {"rating_min": 4})) == [top.pk]
    assert set(ids(api_client.get(URL, {"rating_max": 4}))) == {mid.pk}
    assert set(ids(api_client.get(URL, {"author": user.pk}))) == {top.pk, mid.pk}
    assert api_client.get(URL, {"category": category.pk}).json()["count"] == 3
    assert api_client.get(URL, {"category": 999999}).status_code == 400


def test_ordering_by_rating_puts_unrated_last(api_client, rated_locations):
    top, mid, unrated = rated_locations
    assert ids(api_client.get(URL, {"ordering": "-rating"})) == [top.pk, mid.pk, unrated.pk]
    assert ids(api_client.get(URL, {"ordering": "rating"})) == [mid.pk, top.pk, unrated.pk]


def test_pagination(api_client, make_location, user):
    for i in range(12):
        make_location(user, name=f"Place {i}")
    first = api_client.get(URL)
    second = api_client.get(URL, {"page": 2})

    assert first.json()["count"] == 12
    assert first.json()["next"] is not None
    assert len(ids(first)) == 10 and len(ids(second)) == 2
    assert set(ids(first)).isdisjoint(ids(second))
