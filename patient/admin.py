from django.contrib import admin
from patient.models.client_feedback import ClientFeedback
from patient.models.patient_profile import PatientProfile
from patient.models.medical_history import MedicalHistoryEntry  # Changed from MedicalHistory
from patient.models.health_metric import HealthMetric

@admin.register(ClientFeedback)
class ClientFeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'therapist', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('patient__email', 'therapist__email', 'comments')
    date_hierarchy = 'created_at'

# Register your other models if they're not already registered
admin.site.register(PatientProfile)
admin.site.register(MedicalHistoryEntry)  # Changed from MedicalHistory
admin.site.register(HealthMetric)