from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from borrowings.models import Borrowing
from library.models import Book

User = get_user_model()


class BorrowingApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reader@example.com",
            password="Strong-password-123!",
        )
        self.book = Book.objects.create(
            title="The Hobbit",
            author="J. R. R. Tolkien",
            cover=Book.CoverType.HARD,
            inventory=2,
            daily_fee="1.50",
        )
        self.list_url = reverse("borrowings:borrowing-list")
        self.expected_return_date = timezone.localdate() + timedelta(days=14)
        self.borrowing_data = {
            "book": self.book.id,
            "expected_return_date": self.expected_return_date.isoformat(),
        }

    def test_api_root_lists_available_services(self):
        response = self.client.get("/api/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("books", response.data)
        self.assertIn("borrowings", response.data)
        self.assertIn("payments", response.data)

    def test_borrowings_require_authentication(self):
        response = self.client.get(self.list_url)

        self.assertIn(response.status_code, (401, 403))

    def test_create_borrowing_decreases_inventory_and_attaches_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.list_url,
            self.borrowing_data,
            format="json",
        )

        self.book.refresh_from_db()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"], self.user.id)
        self.assertEqual(response.data["book"]["id"], self.book.id)
        self.assertEqual(self.book.inventory, 1)

    def test_cannot_borrow_book_with_zero_inventory(self):
        self.book.inventory = 0
        self.book.save(update_fields=["inventory"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.list_url,
            self.borrowing_data,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Borrowing.objects.count(), 0)

    def test_user_sees_only_own_borrowings_and_can_filter_active(self):
        active = Borrowing.objects.create(
            book=self.book,
            user=self.user,
            expected_return_date=self.expected_return_date,
        )
        Borrowing.objects.create(
            book=self.book,
            user=self.user,
            expected_return_date=self.expected_return_date,
            actual_return_date=timezone.localdate(),
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="Strong-password-123!",
        )
        Borrowing.objects.create(
            book=self.book,
            user=other_user,
            expected_return_date=self.expected_return_date,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"{self.list_url}?is_active=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [active.id])

    def test_staff_can_filter_borrowings_by_user_id(self):
        staff_user = User.objects.create_user(
            email="librarian@example.com",
            password="Strong-password-123!",
            is_staff=True,
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="Strong-password-123!",
        )
        target = Borrowing.objects.create(
            book=self.book,
            user=other_user,
            expected_return_date=self.expected_return_date,
        )
        self.client.force_authenticate(user=staff_user)

        response = self.client.get(f"{self.list_url}?user_id={other_user.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [target.id])

    def test_return_increments_inventory_and_cannot_be_repeated(self):
        self.client.force_authenticate(user=self.user)
        create_response = self.client.post(
            self.list_url,
            self.borrowing_data,
            format="json",
        )
        return_url = reverse(
            "borrowings:borrowing-return-book",
            args=[create_response.data["id"]],
        )

        response = self.client.post(return_url)
        repeated_response = self.client.post(return_url)

        self.book.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["actual_return_date"],
            timezone.localdate().isoformat(),
        )
        self.assertEqual(repeated_response.status_code, 400)
        self.assertEqual(self.book.inventory, 2)

    def test_expected_return_date_must_be_in_the_future(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.list_url,
            {
                "book": self.book.id,
                "expected_return_date": timezone.localdate().isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
