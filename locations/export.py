"""Location export to CSV / JSON via pandas."""

import pandas as pd
from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone

EXPORT_FORMATS = ("csv", "json")

# queryset field -> column name in the exported file
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
    # .values() -> plain dicts straight from the cursor, no model instances.
    rows = list(qs.values(*EXPORT_COLUMNS))
    df = pd.DataFrame(rows, columns=list(EXPORT_COLUMNS)).rename(columns=EXPORT_COLUMNS)
    # DecimalField -> Decimal objects; cast so both writers emit plain numbers.
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)
    df["rating"] = df["rating"].astype(float).round(2)  # None -> NaN -> empty / null
    df["popularity"] = df["popularity"].astype(float).round(3)
    # Same ISO-8601 UTC string in both formats (CSV and JSON writers would
    # otherwise format datetimes differently).
    for column in ("created_at", "updated_at"):
        df[column] = pd.to_datetime(df[column], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df


def export_response(qs: QuerySet, file_format: str) -> HttpResponse:
    df = build_dataframe(qs)
    filename = f"locations_{timezone.now():%Y%m%d_%H%M%S}.{file_format}"

    if file_format == "csv":
        # BOM so Excel detects UTF-8 and shows Cyrillic correctly.
        content = "﻿" + df.to_csv(index=False)
        content_type = "text/csv; charset=utf-8"
    else:
        content = df.to_json(orient="records", force_ascii=False, indent=2)
        content_type = "application/json; charset=utf-8"

    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
