import pandas as pd
from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone

EXPORT_FORMATS = ("csv", "json")

EXPORT_COLUMNS = {
    "id": "id",
    "name": "name",
    "description": "description",
    "category__name": "category",
    "address": "address",
    "latitude": "latitude",
    "longitude": "longitude",
    "author__username": "author",
    "rating": "rating",
    "reviews_count": "reviews_count",
    "views_7d": "views_7d",
    "popularity": "popularity",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def build_dataframe(qs: QuerySet) -> pd.DataFrame:
    rows = list(qs.values(*EXPORT_COLUMNS))
    df = pd.DataFrame(rows, columns=list(EXPORT_COLUMNS)).rename(columns=EXPORT_COLUMNS)
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)
    df["rating"] = df["rating"].astype(float).round(2)
    df["popularity"] = df["popularity"].astype(float).round(3)
    for column in ("created_at", "updated_at"):
        df[column] = pd.to_datetime(df[column], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df


def export_response(qs: QuerySet, file_format: str) -> HttpResponse:
    df = build_dataframe(qs)
    filename = f"locations_{timezone.now():%Y%m%d_%H%M%S}.{file_format}"

    if file_format == "csv":
        content = "﻿" + df.to_csv(index=False)
        content_type = "text/csv; charset=utf-8"
    else:
        content = df.to_json(orient="records", force_ascii=False, indent=2)
        content_type = "application/json; charset=utf-8"

    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
