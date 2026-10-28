import csv
import io
import json

import pytest
from django.core import mail

pytestmark = pytest.mark.django_db

EXPORT = "/api/locations/export/"


def test_export_csv_respects_filters(api_client, make_location, user):
    make_location(user, name="Ринок")
    make_location(user, name="Other")

    response = api_client.get(EXPORT, {"file_format": "csv", "search": "Ринок"})

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert [row["name"] for row in rows] == ["Ринок"]
    assert rows[0]["category"] == "Parks"


def test_export_json(api_client, location):
    response = api_client.get(EXPORT, {"file_format": "json"})

    data = json.loads(response.content)
    assert data[0]["id"] == location.pk
    assert data[0]["latitude"] == pytest.approx(49.841952)
    assert data[0]["rating"] is None


def test_new_review_notifies_author_and_subscribers(
    client_for, location, make_user, django_capture_on_commit_callbacks
):
    subscriber = make_user()
    reviewer = make_user()
    sub_url = f"/api/locations/{location.pk}/subscribe/"
    assert client_for(subscriber).post(sub_url).status_code == 201
    assert client_for(subscriber).post(sub_url).status_code == 200
    client_for(reviewer).post(sub_url)

    with django_capture_on_commit_callbacks(execute=True):
        client_for(reviewer).post(
            f"/api/locations/{location.pk}/reviews/", {"rating": 5, "text": "Wow"}
        )

    recipients = sorted(message.to[0] for message in mail.outbox)
    assert recipients == sorted([location.author.email, subscriber.email])
