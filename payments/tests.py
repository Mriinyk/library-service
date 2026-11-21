from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.urls import reverse
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from borrowings.models import Borrowing
from library.models import Book
from payments.models import Payment
from payments.services import (
    StripeGatewayError,
    create_checkout_session,
    retrieve_checkout_session,
)

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
        self.assertEqual([item["id"] for item in list_response.data], [self.payment.id])
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
        self.assertEqual(len(response.data), 2)

    def test_payment_endpoints_are_read_only(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.list_url,
            {"status": Payment.Status.PAID},
            format="json",
        )

        self.assertEqual(response.status_code, 405)

    def test_expired_payment_can_be_renewed(self):
        payment = Payment.objects.create(
            status=Payment.Status.EXPIRED,
            type=Payment.PaymentType.PAYMENT,
            borrowing=self.borrowing,
            session_url="https://checkout.stripe.com/c/pay_expired",
            session_id="cs_expired",
            money_to_pay="21.00",
        )
        self.client.force_authenticate(user=self.user)
        session = SimpleNamespace(
            id="cs_renewed",
            url="https://checkout.stripe.com/c/pay_renewed",
        )

        with patch(
            "payments.views.create_checkout_session",
            return_value=session,
        ) as create_session:
            response = self.client.post(
                reverse("payments:payment-renew", args=[payment.id])
            )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.session_id, session.id)
        self.assertEqual(payment.session_url, session.url)
        create_session.assert_called_once()

    def test_non_expired_payment_cannot_be_renewed(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("payments:payment-renew", args=[self.payment.id])
        )

        self.assertEqual(response.status_code, 400)

    def test_stripe_renewal_error_leaves_payment_expired(self):
        payment = Payment.objects.create(
            status=Payment.Status.EXPIRED,
            type=Payment.PaymentType.PAYMENT,
            borrowing=self.borrowing,
            session_url="https://checkout.stripe.com/c/pay_expired",
            session_id="cs_expired_error",
            money_to_pay="21.00",
        )
        self.client.force_authenticate(user=self.user)

        with patch(
            "payments.views.create_checkout_session",
            side_effect=StripeGatewayError("Stripe unavailable"),
        ):
            response = self.client.post(
                reverse("payments:payment-renew", args=[payment.id])
            )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(payment.status, Payment.Status.EXPIRED)

    def test_success_redirect_marks_payment_paid_only_after_stripe_confirms(self):
        url = reverse("payments:payment-success")

        with patch(
            "payments.views.retrieve_checkout_session",
            return_value=SimpleNamespace(payment_status="paid"),
        ):
            response = self.client.get(
                url,
                {"session_id": self.payment.session_id},
            )

        self.payment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.payment.status, Payment.Status.PAID)

    def test_success_redirect_does_not_mark_unpaid_session_paid(self):
        with patch(
            "payments.views.retrieve_checkout_session",
            return_value=SimpleNamespace(payment_status="unpaid"),
        ):
            response = self.client.get(
                reverse("payments:payment-success"),
                {"session_id": self.payment.session_id},
            )

        self.payment.refresh_from_db()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.payment.status, Payment.Status.PENDING)

    def test_cancel_endpoint_returns_paused_message(self):
        response = self.client.get(reverse("payments:payment-cancel"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "Payment was paused.")

    def test_expiration_command_marks_expired_stripe_sessions(self):
        output = StringIO()
        with patch(
            "payments.management.commands.check_expired_payment_sessions."
            "retrieve_checkout_session",
            return_value=SimpleNamespace(status="expired"),
        ):
            call_command("check_expired_payment_sessions", stdout=output)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.EXPIRED)
        self.assertIn("Marked 1 payment(s) as expired.", output.getvalue())

    @override_settings(STRIPE_SECRET_KEY="sk_test_library")
    def test_checkout_session_uses_usd_cents_and_payment_metadata(self):
        session = SimpleNamespace(
            id="cs_created",
            url="https://checkout.stripe.com/c/pay_created",
        )
        with patch(
            "payments.services.stripe.checkout.Session.create",
            return_value=session,
        ) as stripe_create:
            result = create_checkout_session(
                self.payment,
                "https://library.example.com/api/payments/success/",
                "https://library.example.com/api/payments/cancel/",
            )

        self.assertIs(result, session)
        params = stripe_create.call_args.kwargs
        self.assertEqual(params["line_items"][0]["price_data"]["currency"], "usd")
        self.assertEqual(
            params["line_items"][0]["price_data"]["unit_amount"],
            2100,
        )
        self.assertEqual(params["metadata"]["payment_id"], str(self.payment.id))

    @override_settings(STRIPE_SECRET_KEY=None)
    def test_stripe_operations_fail_explicitly_without_api_key(self):
        with self.assertRaises(ImproperlyConfigured):
            retrieve_checkout_session("cs_test_reader")
