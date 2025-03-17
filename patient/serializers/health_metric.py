# patient/serializers/health_metric.py
from rest_framework import serializers
from patient.models.health_metric import HealthMetric


class HealthMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthMetric
        fields = "__all__"
        read_only_fields = ["patient", "timestamp"]
