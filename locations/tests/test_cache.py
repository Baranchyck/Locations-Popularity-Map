import pytest

pytestmark = pytest.mark.django_db

URL = "/api/locations/"


def test_list_is_served_from_cache(api_client, location, django_assert_num_queries):
    api_client.get(URL)
    with django_assert_num_queries(0):
        assert api_client.get(URL).json()["count"] == 1


def test_new_review_invalidates_list(
    api_client, client_for, other_user, location, django_capture_on_commit_callbacks
):
    assert api_client.get(URL).json()["results"][0]["reviews_count"] == 0

    with django_capture_on_commit_callbacks(execute=True):
        client_for(other_user).post(
            f"/api/locations/{location.pk}/reviews/", {"rating": 5, "text": "Great"}
        )

    item = api_client.get(URL).json()["results"][0]
    assert item["reviews_count"] == 1 and item["rating"] == 5.0


def test_update_and_delete_invalidate_list(
    api_client, client_for, location, django_capture_on_commit_callbacks
):
    api_client.get(URL)
    owner = client_for(location.author)

    with django_capture_on_commit_callbacks(execute=True):
        owner.patch(f"{URL}{location.pk}/", {"name": "Renamed"})
    assert api_client.get(URL).json()["results"][0]["name"] == "Renamed"

    with django_capture_on_commit_callbacks(execute=True):
        owner.delete(f"{URL}{location.pk}/")
    assert api_client.get(URL).json()["count"] == 0
