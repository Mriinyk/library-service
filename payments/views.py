from django.db import transaction
from django.urls import reverse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment
from payments.serializers import PaymentSerializer
from payments.services import (
    StripeGatewayError,
    create_checkout_session,
    retrieve_checkout_session,
)


class StripeUnavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Unable to communicate with Stripe."
    default_code = "stripe_unavailable"


class PaymentStateConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The payment state changed during this request."
    default_code = "payment_state_conflict"


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = Payment.objects.select_related(
            "borrowing",
            "borrowing__user",
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(borrowing__user=self.request.user)
        return queryset

    @action(detail=True, methods=("post",), url_path="renew")
    def renew(self, request, *args, **kwargs):
        payment = self.get_object()
        if payment.status != Payment.Status.EXPIRED:
            raise serializers.ValidationError(
                {"status": "Only expired payments can be renewed."}
            )

        success_url = request.build_absolute_uri(
            reverse("payments:payment-success")
        )
        success_url = f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = request.build_absolute_uri(
            reverse("payments:payment-cancel")
        )

        try:
            session = create_checkout_session(payment, success_url, cancel_url)
        except StripeGatewayError as exc:
            raise StripeUnavailable() from exc

        with transaction.atomic():
            updated = Payment.objects.filter(
                pk=payment.pk,
                status=Payment.Status.EXPIRED,
            ).update(
                status=Payment.Status.PENDING,
                session_url=session.url,
                session_id=session.id,
            )

        if not updated:
            raise PaymentStateConflict()

        payment.refresh_from_db()
        return Response(PaymentSerializer(payment).data)


class PaymentSuccessView(APIView):
    permission_classes = ()

    def get(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            raise serializers.ValidationError(
                {"session_id": "This query parameter is required."}
            )

        payment = Payment.objects.filter(session_id=session_id).first()
        if payment is None:
            return Response(
                {"detail": "Payment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            session = retrieve_checkout_session(session_id)
        except StripeGatewayError as exc:
            raise StripeUnavailable() from exc

        if session.payment_status != "paid":
            return Response(
                {"detail": "Stripe has not confirmed this payment."},
                status=status.HTTP_409_CONFLICT,
            )

        Payment.objects.filter(
            pk=payment.pk,
            session_id=session_id,
            status__in=(Payment.Status.PENDING, Payment.Status.EXPIRED),
        ).update(status=Payment.Status.PAID)

        payment.refresh_from_db()
        if payment.status != Payment.Status.PAID:
            return Response(
                {"detail": "This payment session is no longer active."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"detail": "Payment successful."})


class PaymentCancelView(APIView):
    permission_classes = ()

    def get(self, request):
        return Response({"detail": "Payment was paused."})
