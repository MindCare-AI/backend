# Generated migration to fix experience field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('therapist', '0001_initial'),
    ]

    operations = [
        # Allow NULL values for experience field and set default for existing records
        migrations.RunSQL(
            """
            -- Allow NULL values for experience field
            ALTER TABLE therapist_therapistprofile 
            ALTER COLUMN experience DROP NOT NULL;
            
            -- Update existing NULL records to empty JSON array
            UPDATE therapist_therapistprofile 
            SET experience = '[]'::jsonb 
            WHERE experience IS NULL;
            """,
            reverse_sql="""
            -- Set all NULL values to empty array before making NOT NULL
            UPDATE therapist_therapistprofile 
            SET experience = '[]'::jsonb 
            WHERE experience IS NULL;
            
            -- Make the field NOT NULL again
            ALTER TABLE therapist_therapistprofile 
            ALTER COLUMN experience SET NOT NULL;
            """
        ),
    ]
