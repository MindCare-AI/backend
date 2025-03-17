# notifications/services/email_service.py
from django.conf import settings
from django.core.exceptions import ValidationError
from templated_email import send_templated_mail
import logging
import re
from typing import Dict, Any
from ..models import Notification, User

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def send_email(
        user: "User",
        template_name: str,
        context: Dict[str, Any],
        fail_silently: bool = False,
    ) -> None:
        """Generic email sending method"""
        try:
            context.update(
                {
                    "recipient_name": user.get_full_name() or user.username,
                    "site_url": settings.SITE_URL,
                }
            )

            send_templated_mail(
                template_name=template_name,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                context=context,
                fail_silently=fail_silently,
            )
            logger.info("Email sent successfully to %s", user.email)

        except Exception as e:
            logger.error("Email send failed: %s", e)
            if not fail_silently:
                raise e

    @staticmethod
    def send_notification_email(notification: Notification) -> None:
        try:
            context = {
                "notification": notification,
            }

            if not all(
                [settings.EMAIL_HOST, settings.EMAIL_PORT, settings.DEFAULT_FROM_EMAIL]
            ):
                raise ValidationError("Email settings not configured")

            EmailService.send_email(
                user=notification.user,
                template_name=notification.notification_type.template_name,
                context=context,
                fail_silently=False,
            )

        except ValidationError as ve:
            logger.exception("Validation error when sending notification email")
            raise ve
        except Exception as e:
            logger.exception("Error sending notification email")
            raise e

    @staticmethod
    def send_verification_email(user: "User", verification_code: str) -> None:
        """
        Send a verification email to the user with the provided verification code.

        Args:
            user: The user to send the email to.
            verification_code: The verification code to include in the email.

        Raises:
            ValidationError: If the verification code is invalid.
        """
        if not EmailService.validate_verification_code(verification_code):
            raise ValidationError("Invalid verification code.")

        context = {
            "recipient": user,
            "verification_code": verification_code,
        }
        EmailService.send_email(
            user=user,
            template_name="notifications/verification_email.email",
            context=context,
        )

    @staticmethod
    def validate_verification_code(code: str) -> bool:
        """Validate the verification code."""
        # Basic example: verification code must be 6 alphanumeric characters.
        if re.fullmatch(r"[A-Za-z0-9]{6}", code):
            return True
        return False
