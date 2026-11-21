from django.core.management.base import BaseCommand

from payments.models import Payment
from payments.services import retrieve_checkout_session


class Command(BaseCommand):
    help = "Mark payments with expired Stripe checkout sessions as expired."

    def handle(self, *args, **options):
        expired_count = 0
        pending_payments = Payment.objects.filter(status=Payment.Status.PENDING)

        for payment in pending_payments.iterator():
            session = retrieve_checkout_session(payment.session_id)
            if session.status == "expired":
                expired_count += Payment.objects.filter(
                    pk=payment.pk,
                    status=Payment.Status.PENDING,
                ).update(status=Payment.Status.EXPIRED)

        self.stdout.write(
            self.style.SUCCESS(
                f"Marked {expired_count} payment(s) as expired."
            )
        )
