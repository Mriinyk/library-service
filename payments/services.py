from decimal import Decimal

import stripe
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class StripeGatewayError(Exception):
    pass


def _configure_stripe():
    if not settings.STRIPE_SECRET_KEY:
        raise ImproperlyConfigured("Set the STRIPE_SECRET_KEY environment variable.")
    stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(payment, success_url, cancel_url):
    _configure_stripe()
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": (
                                f"{payment.get_type_display()} for borrowing "
                                f"#{payment.borrowing_id}"
                            ),
                        },
                        "unit_amount": int(Decimal(str(payment.money_to_pay)) * 100),
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(payment.pk),
            metadata={"payment_id": str(payment.pk)},
        )
    except stripe.StripeError as exc:
        raise StripeGatewayError("Stripe could not create a checkout session.") from exc

    if not session.id or not session.url:
        raise StripeGatewayError("Stripe returned an incomplete checkout session.")
    return session


def retrieve_checkout_session(session_id):
    _configure_stripe()
    try:
        return stripe.checkout.Session.retrieve(session_id)
    except stripe.StripeError as exc:
        raise StripeGatewayError(
            "Stripe could not retrieve the checkout session."
        ) from exc
