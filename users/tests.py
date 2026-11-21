from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

User = get_user_model()


class UserApiTests(APITestCase):
    def setUp(self):
        self.user_data = {
            "email": "reader@example.com",
            "first_name": "Book",
            "last_name": "Reader",
            "password": "Strong-password-123!",
        }

    def test_registration_creates_user_without_staff_access(self):
        response = self.client.post(
            reverse("users:register"),
            {**self.user_data, "is_staff": True},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email=self.user_data["email"])
        self.assertTrue(user.check_password(self.user_data["password"]))
        self.assertFalse(user.is_staff)
        self.assertNotIn("password", response.data)

    def test_registration_rejects_duplicate_email(self):
        User.objects.create_user(**self.user_data)

        response = self.client.post(
            reverse("users:register"),
            self.user_data,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_registration_requires_password(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "email": self.user_data["email"],
                "first_name": self.user_data["first_name"],
                "last_name": self.user_data["last_name"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email=self.user_data["email"]).exists())

    def test_user_can_access_profile_with_standard_authorization_header(self):
        user = User.objects.create_user(**self.user_data)
        token_response = self.client.post(
            reverse("users:token_obtain_pair"),
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}"
        )

        response = self.client.get(reverse("users:me"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], user.id)

    def test_user_can_refresh_access_token(self):
        User.objects.create_user(**self.user_data)
        token_response = self.client.post(
            reverse("users:token_obtain_pair"),
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
            format="json",
        )

        response = self.client.post(
            reverse("users:token_refresh"),
            {"refresh": token_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_profile_update_can_change_password_without_exposing_it(self):
        user = User.objects.create_user(**self.user_data)
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse("users:me"),
            {"first_name": "Updated", "password": "Different-password-456!"},
            format="json",
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.first_name, "Updated")
        self.assertTrue(user.check_password("Different-password-456!"))
        self.assertNotIn("password", response.data)

    def test_profile_put_does_not_require_password(self):
        user = User.objects.create_user(**self.user_data)
        self.client.force_authenticate(user=user)

        response = self.client.put(
            reverse("users:me"),
            {
                "email": self.user_data["email"],
                "first_name": "Updated",
                "last_name": self.user_data["last_name"],
            },
            format="json",
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.first_name, "Updated")
        self.assertTrue(user.check_password(self.user_data["password"]))
