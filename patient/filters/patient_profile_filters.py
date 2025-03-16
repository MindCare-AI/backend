# patient/filters/patient_profile_filters.py
from django.db.models import Q
from django_filters import rest_framework as django_filters
from patient.models.patient_profile import PatientProfile


class PatientProfileFilter(django_filters.FilterSet):
    blood_type = django_filters.CharFilter(lookup_expr="exact")
    condition = django_filters.CharFilter(method="filter_condition")
    appointment_after = django_filters.DateTimeFilter(
        field_name="next_appointment", lookup_expr="gte"
    )

    class Meta:
        model = PatientProfile
        fields = ["blood_type", "condition", "appointment_after"]

    def filter_condition(self, queryset, name, value):
        return queryset.filter(
            Q(medical_history__icontains=value)
            | Q(current_medications__icontains=value)
        )
