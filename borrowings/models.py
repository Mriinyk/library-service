from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from library.models import Book


class Borrowing(models.Model):
    borrow_date = models.DateField(default=timezone.localdate)
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(blank=True, null=True)
    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name="borrowings",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrowings",
    )

    class Meta:
        ordering = ("-borrow_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(expected_return_date__gt=F("borrow_date")),
                name="borrowing_expected_after_borrow",
            ),
            models.CheckConstraint(
                condition=Q(actual_return_date__isnull=True)
                | Q(actual_return_date__gte=F("borrow_date")),
                name="borrowing_actual_not_before_borrow",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "actual_return_date"),
                name="borrowing_user_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.book} borrowed by {self.user} on {self.borrow_date}"

    def clean(self):
        super().clean()
        if (
            self.expected_return_date
            and self.borrow_date
            and self.expected_return_date <= self.borrow_date
        ):
            raise ValidationError(
                {
                    "expected_return_date": (
                        "Expected return date must be after the borrowing date."
                    )
                }
            )
