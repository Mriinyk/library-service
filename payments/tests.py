from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from borrowings.models import Borrowing
from library.models import Book
from payments.models import Payment

User = get_user_model()


class PaymentApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reader@example.com",
            password="Strong-password-123!",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Strong-password-123!",
        )
        self.book = Book.objects.create(
            title="The Hobbit",
            author="J. R. R. Tolkien",
            cover=Book.CoverType.HARD,
            inventory=1,
            daily_fee="1.50",
        )
        expected_return_date = timezone.localdate() + timedelta(days=14)
        self.borrowing = Borrowing.objects.create(
            book=self.book,
            user=self.user,
            expected_return_date=expected_return_date,
        )
        self.other_borrowing = Borrowing.objects.create(
            book=self.book,
            user=self.other_user,
            expected_return_date=expected_return_date,
        )
        self.payment = Payment.objects.create(
            status=Payment.Status.PENDING,
            type=Payment.PaymentType.PAYMENT,
            borrowing=self.borrowing,
            session_url="https://checkout.stripe.com/c/pay_test",
            session_id="cs_test_reader",
            money_to_pay="21.00",
        )
        self.other_payment = Payment.objects.create(
            status=Payment.Status.PAID,
            type=Payment.PaymentType.FINE,
            borrowing=self.other_borrowing,
            session_url="https://checkout.stripe.com/c/pay_other",
            session_id="cs_test_other",
            money_to_pay="3.00",
        )
        self.list_url = reverse("payments:payment-list")

    def test_payments_require_authentication(self):
        response = self.client.get(self.list_url)

        self.assertIn(response.status_code, (401, 403))

    def test_user_can_list_and_retrieve_only_own_payments(self):
        self.client.force_authenticate(user=self.user)
        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(
            reverse("payments:payment-detail", args=[self.payment.id])
        )
        other_detail_response = self.client.get(
            reverse("payments:payment-detail", args=[self.other_payment.id])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(
            [item["id"] for item in list_response.data["results"]],
            [self.payment.id],
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["borrowing"], self.borrowing.id)
        self.assertEqual(detail_response.data["money_to_pay"], "21.00")
        self.assertEqual(other_detail_response.status_code, 404)

    def test_staff_can_list_all_payments(self):
        staff_user = User.objects.create_user(
            email="librarian@example.com",
            password="Strong-password-123!",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_payment_endpoints_are_read_only(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.list_url,
            {"status": Payment.Status.PAID},
            format="json",
        )

        self.assertEqual(response.status_code, 405)
