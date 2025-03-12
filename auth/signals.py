# auth\signals.py
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from allauth.account.signals import email_confirmation_sent, user_signed_up
from django.core.mail import send_mail
import logging

User = get_user_model()

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def clear_permissions_on_registration(sender, instance, created, **kwargs):
    if created:
        # Only remove non-group permissions
        user_permissions = instance.user_permissions.all()
        group_permissions = Permission.objects.filter(group__user=instance)
        to_remove = user_permissions.exclude(
            id__in=group_permissions.values_list("id", flat=True)
        )
        instance.user_permissions.remove(*to_remove)


@receiver(m2m_changed, sender=User.groups.through)
def sync_group_permissions(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.user_permissions.clear()
        group_permissions = Permission.objects.filter(group__user=instance)
        instance.user_permissions.set(group_permissions)


@receiver(user_signed_up)
def handle_user_signed_up(request, user, **kwargs):
    """Log when a user signs up and send welcome email"""
    logger.info(f"New user signed up: {user.email}")
    try:
        send_mail(
            "Welcome to MindCare",
            "Thank you for registering! Please verify your email to continue.",
            "azizbahloulextra@gmail.com",
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")


@receiver(email_confirmation_sent)
def log_email_confirmation_sent(request, email_address, **kwargs):
    """Log when verification email is sent"""
    logger.info(f"Verification email sent to: {email_address.email}")
