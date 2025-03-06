# auth\signals.py
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

User = get_user_model()

@receiver(post_save, sender=User)
def clear_permissions_on_registration(sender, instance, created, **kwargs):
    if created:
        instance.user_permissions.clear()
        group_permissions = Permission.objects.filter(group__user=instance)
        instance.user_permissions.set(group_permissions)

@receiver(m2m_changed, sender=User.groups.through)
def sync_group_permissions(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.user_permissions.clear()
        group_permissions = Permission.objects.filter(group__user=instance)
        instance.user_permissions.set(group_permissions)