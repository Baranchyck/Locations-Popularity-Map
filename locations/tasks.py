from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .models import Review

User = get_user_model()


@shared_task(autoretry_for=(SMTPException, OSError), retry_backoff=True, max_retries=3)
def send_email(subject: str, message: str, recipient: str) -> None:
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient])


@shared_task
def notify_new_review(review_id: int) -> None:
    review = (
        Review.objects.select_related("author", "location", "location__author")
        .filter(pk=review_id)
        .first()
    )
    if review is None:
        return

    location = review.location
    summary = (
        f"{review.author.username} rated \"{location.name}\" {review.rating}/5:\n\n"
        f"{review.text}\n"
    )

    owner = location.author
    if owner and owner.pk != review.author_id and owner.email:
        send_email.delay(f'New review on your location "{location.name}"', summary, owner.email)

    subscribers = (
        User.objects.filter(location_subscriptions__location=location, is_active=True)
        .exclude(pk=review.author_id)
        .exclude(pk=location.author_id or 0)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    for email in subscribers:
        send_email.delay(f'New review on "{location.name}"', summary, email)
