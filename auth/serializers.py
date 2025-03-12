from dj_rest_auth.serializers import (
    PasswordResetConfirmSerializer,
    UserDetailsSerializer,
)
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django_otp.plugins.otp_totp.models import TOTPDevice

UserModel = get_user_model()


class CustomPasswordResetConfirmSerializer(PasswordResetConfirmSerializer):
    new_password1 = serializers.CharField(
        max_length=128,
        write_only=True,
        label="New Password",
        style={"input_type": "password"},
    )
    new_password2 = serializers.CharField(
        max_length=128,
        write_only=True,
        label="Confirm New Password",
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        password1 = attrs.get("new_password1")
        password2 = attrs.get("new_password2")
        if password1 != password2:
            raise serializers.ValidationError(
                {"new_password2": "The two password fields didn't match."}
            )
        return super().validate(attrs)

    def save(self):
        if self.set_password_form.is_valid():
            self.set_password_form.save()
            return self.set_password_form.user
        raise serializers.ValidationError(
            "An error occurred while resetting the password."
        )


class CustomUserDetailsSerializer(UserDetailsSerializer):
    class Meta(UserDetailsSerializer.Meta):
        fields = UserDetailsSerializer.Meta.fields + ("first_name", "last_name")


class ConfirmEmailSerializer(serializers.Serializer):
    key = serializers.CharField()


class GoogleAuthSerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.CharField(required=False)


class Enable2FASerializer(serializers.Serializer):
    enable_2fa = serializers.BooleanField(required=True)

    def save(self, user):
        if self.validated_data["enable_2fa"]:
            TOTPDevice.objects.get_or_create(user=user, confirmed=True)
        else:
            TOTPDevice.objects.filter(user=user).delete()
