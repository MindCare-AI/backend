#auth\registration\serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from allauth.account.adapter import get_adapter
from allauth.account.utils import setup_user_email
from dj_rest_auth.registration.serializers import RegisterSerializer

class CustomRegisterSerializer(RegisterSerializer):
    """
    Custom serializer for user registration in Mindcare.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)  # ensure email is required
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    role = serializers.ChoiceField(
        choices=[("patient", "Patient"), ("therapist", "Therapist")],
        required=True
    )

    class Meta:
        model = get_user_model()
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "role",
        ]
    
    def validate_email(self, value):
        # Check if the email already exists (case-insensitive)
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user is already registered with that email address.")
        return value

    def validate_role(self, value):
        """Ensure the role is lowercase so group matching works properly."""
        return value.lower()

    def get_cleaned_data(self):
        # If username is not provided, fallback to email:
        username = self.validated_data.get("username")
        if not username or not username.strip():
            username = self.validated_data.get("email")
        return {
            "username": username.strip() if username else "",
            "first_name": self.validated_data.get("first_name", ""),
            "last_name": self.validated_data.get("last_name", ""),
            "password1": self.validated_data.get("password1", ""),
            "email": self.validated_data.get("email", ""),
            "role": self.validated_data.get("role", ""),
        }

    def custom_signup(self, request, user):
        user.first_name = self.cleaned_data.get("first_name")
        user.last_name = self.cleaned_data.get("last_name")
        role = self.cleaned_data.get("role")
        if role == "patient":
            patient_group, _ = Group.objects.get_or_create(name="Patient")
            user.groups.add(patient_group)
        elif role == "therapist":
            therapist_group, _ = Group.objects.get_or_create(name="Therapist")
            user.groups.add(therapist_group)
        user.save()

    def save(self, request):
        adapter = get_adapter()
        user = adapter.new_user(request)
        self.cleaned_data = self.get_cleaned_data()
        user.username = self.cleaned_data.get("username")
        user = adapter.save_user(request, user, self)
        self.custom_signup(request, user)
        user.save()
        setup_user_email(request, user, [])
        return user
