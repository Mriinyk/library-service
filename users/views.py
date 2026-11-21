from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.serializers import UserSerializer


@extend_schema(tags=["Users"])
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = (AllowAny,)


@extend_schema(tags=["Users"])
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


@extend_schema(tags=["Users"])
class UserTokenObtainPairView(TokenObtainPairView):
    permission_classes = (AllowAny,)


@extend_schema(tags=["Users"])
class UserTokenRefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)
