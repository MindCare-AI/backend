#!/usr/bin/env python3
"""
Clean up test data from production database
"""
import os
import sys

# Add the backend directory to Python path
sys.path.append('/home/siaziz/Desktop/backend')

# Setup Django
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mindcare.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.utils import ProgrammingError

User = get_user_model()

def safe_delete_related_data(user_id):
    """Safely delete related data, handling missing tables"""
    deleted_counts = {}
    
    # List of tables that might have test data
    related_tables = [
        ('datawarehouse_userdatasnapshot', 'user_id'),
        ('datawarehouse_aianalysisdataset', 'user_id'),
        ('datawarehouse_unifieddatacollection', 'user_id'),
    ]
    
    for table_name, user_column in related_tables:
        try:
            with connection.cursor() as cursor:
                if user_column:
                    cursor.execute(f"DELETE FROM {table_name} WHERE {user_column} = %s", [user_id])
                    deleted_counts[table_name] = cursor.rowcount
                    if cursor.rowcount > 0:
                        print(f"  - Deleted {cursor.rowcount} records from {table_name}")
                        
        except ProgrammingError as e:
            if "does not exist" in str(e):
                print(f"  - Skipping {table_name} (table does not exist)")
            else:
                print(f"  - Error with {table_name}: {e}")
        except Exception as e:
            print(f"  - Unexpected error with {table_name}: {e}")
    
    return deleted_counts

def cleanup_test_data():
    """Remove test data from production database"""
    print("🧹 Cleaning up test data...")
    
    # Find test user
    test_user = User.objects.filter(email='test_datawarehouse@example.com').first()
    
    if test_user:
        print(f"Found test user: {test_user.email} (ID: {test_user.id})")
        
        try:
            # Safely delete related data first
            print("Cleaning up related data...")
            safe_delete_related_data(test_user.id)
            
            # Delete the user using Django ORM but handle foreign key issues
            user_email = test_user.email
            user_id = test_user.id
            
            # Try to delete user, but if it fails due to missing tables, use raw SQL
            try:
                test_user.delete()
                print(f"Deleted test user: {user_email} (ID: {user_id})")
            except ProgrammingError as e:
                if "does not exist" in str(e):
                    print(f"Using direct SQL to delete user due to missing related tables...")
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM auth_user WHERE id = %s", [user_id])
                        print(f"Deleted test user via SQL: {user_email} (ID: {user_id})")
                else:
                    raise e
            
            print("✅ Test data cleanup completed!")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            
    else:
        print("❌ Test user not found in database")

if __name__ == "__main__":
    cleanup_test_data()

if __name__ == "__main__":
    cleanup_test_data()
