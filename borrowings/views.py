from django.db import transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from borrowings.models import Borrowing
from borrowings.serializers import BorrowingCreateSerializer, BorrowingReadSerializer
from library.models import Book


@extend_schema(tags=["Borrowings"])
class BorrowingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Borrowing.objects.all()
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = Borrowing.objects.select_related("book", "user")
        user = self.request.user

        if not user.is_staff:
            queryset = queryset.filter(user=user)

        if self.action != "list":
            return queryset

        if user.is_staff and "user_id" in self.request.query_params:
            user_id = self.request.query_params["user_id"]
            try:
                user_id = int(user_id)
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"user_id": "Must be a valid integer."}
                ) from exc
            if user_id < 1:
                raise serializers.ValidationError(
                    {"user_id": "Must be a positive integer."}
                )
            queryset = queryset.filter(user_id=user_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            value = is_active.lower()
            if value not in ("true", "false"):
                raise serializers.ValidationError(
                    {"is_active": "Use 'true' or 'false'."}
                )
            queryset = queryset.filter(
                actual_return_date__isnull=(value == "true")
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return BorrowingCreateSerializer
        return BorrowingReadSerializer

    @extend_schema(
        tags=["Borrowings"],
        parameters=[
            OpenApiParameter(
                "is_active",
                bool,
                OpenApiParameter.QUERY,
                description="Filter by return status.",
            ),
            OpenApiParameter(
                "user_id",
                int,
                OpenApiParameter.QUERY,
                description="Staff-only filter for a customer's borrowings.",
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Borrowings"],
        request=BorrowingCreateSerializer,
        responses={201: BorrowingReadSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        borrowing = serializer.save(user=request.user)
        response_data = BorrowingReadSerializer(
            borrowing,
            context=self.get_serializer_context(),
        ).data
        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data),
        )

    @extend_schema(
        tags=["Borrowings"],
        request=None,
        responses=BorrowingReadSerializer,
    )
    @action(detail=True, methods=("post",), url_path="return")
    def return_book(self, request, *args, **kwargs):
        borrowing = self.get_object()
        with transaction.atomic():
            returned = Borrowing.objects.filter(
                pk=borrowing.pk,
                actual_return_date__isnull=True,
            ).update(actual_return_date=timezone.localdate())

            if not returned:
                raise serializers.ValidationError(
                    {"detail": "This borrowing has already been returned."}
                )

            Book.objects.filter(pk=borrowing.book_id).update(
                inventory=F("inventory") + 1
            )

        borrowing.refresh_from_db()
        return Response(BorrowingReadSerializer(borrowing).data)
