# notifications/filters.py
import django_filters
from .models import Notification


class NotificationFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category", lookup_expr="exact")
    is_read = django_filters.BooleanFilter(field_name="is_read")
    priority = django_filters.CharFilter(field_name="priority", lookup_expr="iexact")
    created_at = django_filters.DateFromToRangeFilter(field_name="created_at")

    class Meta:
        model = Notification
        fields = ["category", "is_read", "priority", "created_at"]
