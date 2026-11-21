from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from borrowings.models import Borrowing
from library.models import Book
from library.serializers import BookSerializer


class BorrowingReadSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    user = serializers.IntegerField(source="user_id", read_only=True)

    class Meta:
        model = Borrowing
        fields = (
            "id",
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
            "user",
        )
        read_only_fields = fields


class BorrowingCreateSerializer(serializers.ModelSerializer):
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())

    class Meta:
        model = Borrowing
        fields = ("book", "expected_return_date")

    def validate_expected_return_date(self, value):
        try:
            Borrowing(expected_return_date=value).clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return value

    def create(self, validated_data):
        with transaction.atomic():
            book = validated_data["book"]
            inventory_updated = Book.objects.filter(
                pk=book.pk,
                inventory__gt=0,
            ).update(inventory=F("inventory") - 1)

            if not inventory_updated:
                raise serializers.ValidationError(
                    {"book": "This book is out of stock."}
                )

            return Borrowing.objects.create(**validated_data)
