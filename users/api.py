from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from rest_framework import status
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserProfileSerializer


class MeAPIView(RetrieveUpdateDestroyAPIView):
    """GET / PUT / PATCH / DELETE the *current* account.

    There is no user id in the URL: get_object() returns request.user, which is
    the entire tenancy boundary. One account can never address another.
    """

    # Stricter than the project default (IsAuthenticatedOrReadOnly), which would
    # let anonymous visitors read.
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def destroy(self, request, *args, **kwargs):
        """Soft delete: deactivate, keep the row.

        Requires the password -- deactivation is destructive and an unattended
        logged-in browser should not be enough. is_active=False already blocks
        login through Django's ModelBackend, so no further gate is needed.
        """
        user = request.user
        password = request.data.get('password', '')

        if not password:
            return Response(
                {'password': 'Enter your password to deactivate your account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.check_password(password):
            return Response(
                {'password': 'Incorrect password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = False
        user.save(update_fields=['is_active'])
        logout(request)  # the session must not outlive the account
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordAPIView(APIView):
    """POST a password change for the current account.

    Separate from the profile representation on purpose: a profile PUT must
    never be able to touch the password.

    PasswordChangeForm checks the old password and runs the
    AUTH_PASSWORD_VALIDATORS from settings. form.save() hashes -- nothing here
    ever touches a raw password hash itself.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        form = PasswordChangeForm(user=request.user, data=request.data)

        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

        user = form.save()
        # Without this the session's auth hash goes stale and the user is
        # silently logged out the instant they change their own password.
        update_session_auth_hash(request, user)
        return Response({'detail': 'Password updated.'}, status=status.HTTP_200_OK)
