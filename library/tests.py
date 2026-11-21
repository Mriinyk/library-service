from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from library.models import Book

User = get_user_model()


class BookApiTests(APITestCase):
    def setUp(self):
        self.book_data = {
            "title": "The Hobbit",
            "author": "J. R. R. Tolkien",
            "cover": Book.CoverType.HARD,
            "inventory": 2,
            "daily_fee": "1.50",
        }
        self.book = Book.objects.create(**self.book_data)
        self.list_url = reverse("library:book-list")
        self.detail_url = reverse("library:book-detail", args=[self.book.id])

    def test_anyone_can_list_and_retrieve_books(self):
        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(self.detail_url)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["title"], self.book.title)
        self.assertEqual(detail_response.data["daily_fee"], "1.50")

    def test_anonymous_users_cannot_modify_books(self):
        response = self.client.post(
            self.list_url,
            {**self.book_data, "title": "Unauthorized"},
            format="json",
        )

        self.assertIn(response.status_code, (401, 403))

    def test_regular_users_cannot_modify_books(self):
        user = User.objects.create_user(
            email="reader@example.com",
            password="Strong-password-123!",
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            self.detail_url,
            {"title": "Changed title"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_staff_users_can_create_update_and_delete_books(self):
        staff_user = User.objects.create_user(
            email="librarian@example.com",
            password="Strong-password-123!",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)

        create_response = self.client.post(
            self.list_url,
            {**self.book_data, "title": "Another Book"},
            format="json",
        )
        new_book_id = create_response.data["id"]
        detail_url = reverse("library:book-detail", args=[new_book_id])

        update_response = self.client.patch(
            detail_url,
            {"inventory": 0},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["inventory"], 0)
        self.assertEqual(delete_response.status_code, 204)

    def test_book_fields_are_validated(self):
        staff_user = User.objects.create_user(
            email="librarian@example.com",
            password="Strong-password-123!",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)

        for invalid_data in (
            {"cover": "PAPER"},
            {"inventory": -1},
            {"daily_fee": "0.00"},
        ):
            response = self.client.post(
                self.list_url,
                {**self.book_data, **invalid_data, "title": "Invalid Book"},
                format="json",
            )
            self.assertEqual(response.status_code, 400, invalid_data)
