from rest_framework import serializers

from .models import CustomUser


class UserProfileSerializer(serializers.ModelSerializer):
    """The account as its owner sees it.

    `username` and `email` are exposed for display but marked read-only, so a
    forged PUT/PATCH carrying them is silently ignored rather than honoured.
    Both are unique=True, so allowing edits would need collision handling --
    deliberately out of scope.
    """

    class Meta:
        model = CustomUser
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'address',
            'date_joined',
            'is_active',
        ]
        read_only_fields = ['username', 'email', 'date_joined', 'is_active']
