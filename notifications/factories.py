# notifications/factories.py
import factory
from django.contrib.auth import get_user_model
from .models import Notification, NotificationType, NotificationPreference

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    password = "password123"

    @factory.post_generation
    def set_password(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.set_password(extracted)
            self.save()


class NotificationTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationType

    name = factory.Sequence(lambda n: f"NotificationType{n}")
    description = "A test notification type."
    template_name = "notifications/test_template.html"
    is_active = True


class NotificationPreferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NotificationPreference

    user = factory.SubFactory(UserFactory)
    email_notifications = True
    in_app_notifications = True


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    notification_type = factory.SubFactory(NotificationTypeFactory)
    title = "Factory Test Notification"
    message = "This notification is created via Factory Boy."
    priority = "high"
    category = "tests"
    is_read = False
    link = "http://example.com"
    metadata = {"key": "value"}
