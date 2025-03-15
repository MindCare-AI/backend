from django.db import migrations, models
from django.utils import timezone


def set_default_timestamps(apps, schema_editor):
    PatientProfile = apps.get_model("patient", "PatientProfile")
    default_time = timezone.now()

    # Update all existing records with default timestamp
    PatientProfile.objects.all().update(
        created_at=default_time, updated_at=default_time
    )


class Migration(migrations.Migration):
    dependencies = [
        ("patient", "0003_moodlog"),  # Updated to correct dependency
    ]

    operations = [
        migrations.AddField(
            model_name="patientprofile",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="patientprofile",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(set_default_timestamps),
    ]
