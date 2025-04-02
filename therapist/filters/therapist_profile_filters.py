# therapist/filters/therapist_profile_filters.py
from django_filters import rest_framework as django_filters
from therapist.models.therapist_profile import TherapistProfile


class TherapistProfileFilter(django_filters.FilterSet):
    specialization = django_filters.CharFilter(lookup_expr="icontains")
    languages = django_filters.CharFilter(method="filter_languages")
    available_day = django_filters.CharFilter(method="filter_available_day")

    class Meta:
        model = TherapistProfile
        fields = ["specialization", "languages", "available_day"]

    def filter_languages(self, queryset, name, value):
        return queryset.filter(languages_spoken__contains=value.split(","))

    def filter_available_day(self, queryset, name, value):
        return queryset.filter(available_days__has_key=value.lower())
    