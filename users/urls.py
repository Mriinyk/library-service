from django.urls import path
from users.views import (
    UserProfileView,
    UserRegistrationView,
    UserTokenObtainPairView,
    UserTokenRefreshView,
)

app_name = "users"

urlpatterns = [
    path("", UserRegistrationView.as_view(), name="register"),
    path("token/", UserTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", UserTokenRefreshView.as_view(), name="token_refresh"),
    path("me/", UserProfileView.as_view(), name="me"),
]
