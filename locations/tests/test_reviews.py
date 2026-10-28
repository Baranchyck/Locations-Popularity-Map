import pytest

from locations.models import ReviewVote

pytestmark = pytest.mark.django_db


def reviews_url(location):
    return f"/api/locations/{location.pk}/reviews/"


def vote_url(review_id):
    return f"/api/reviews/{review_id}/vote/"


@pytest.fixture
def review(client_for, other_user, location, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(other_user).post(
            reviews_url(location), {"rating": 4, "text": "Nice place"}
        )
    assert response.status_code == 201
    return response.json()


def test_anonymous_cannot_review(api_client, location):
    assert api_client.post(reviews_url(location), {"rating": 5, "text": "x"}).status_code == 403


def test_rating_must_be_between_1_and_5(client_for, user, location):
    for rating in (0, 6):
        response = client_for(user).post(reviews_url(location), {"rating": rating, "text": "x"})
        assert response.status_code == 400


def test_second_review_by_same_user_is_conflict(client_for, other_user, location, review):
    response = client_for(other_user).post(reviews_url(location), {"rating": 1, "text": "again"})
    assert response.status_code == 409


def test_only_author_can_edit_review(client_for, user, other_user, review):
    url = f"/api/reviews/{review['id']}/"
    assert client_for(user).patch(url, {"rating": 1}).status_code == 403
    assert client_for(other_user).patch(url, {"rating": 2}).json()["rating"] == 2


def test_like_switch_and_withdraw_vote(client_for, user, review):
    client = client_for(user)

    first = client.post(vote_url(review["id"]), {"value": 1})
    assert first.status_code == 201
    assert (first.json()["likes"], first.json()["my_vote"]) == (1, 1)

    switched = client.post(vote_url(review["id"]), {"value": -1})
    assert switched.status_code == 200
    assert (switched.json()["likes"], switched.json()["dislikes"]) == (0, 1)
    assert ReviewVote.objects.filter(review_id=review["id"]).count() == 1

    assert client.delete(vote_url(review["id"])).status_code == 204
    assert client.delete(vote_url(review["id"])).status_code == 404


def test_cannot_vote_for_own_review(client_for, other_user, review):
    assert client_for(other_user).post(vote_url(review["id"]), {"value": 1}).status_code == 400
