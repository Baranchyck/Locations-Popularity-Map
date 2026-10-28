from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


@shared_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    max_retries=3,
)
def send_password_reset_email(user_id: int) -> None:
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = settings.PASSWORD_RESET_URL.format(uid=uid, token=token)

    send_mail(
        subject="Password reset",
        message=(
            f"Hi {user.username},\n\n"
            f"To set a new password follow the link:\n{link}\n\n"
            f"Or call POST /api/auth/password-reset/confirm/ with:\n"
            f"uid: {uid}\ntoken: {token}\n\n"
            "If you did not request a password reset, just ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
