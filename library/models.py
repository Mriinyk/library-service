from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Book(models.Model):
    class CoverType(models.TextChoices):
        HARD = "HARD", "Hardcover"
        SOFT = "SOFT", "Softcover"

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    cover = models.CharField(max_length=4, choices=CoverType.choices)
    inventory = models.PositiveIntegerField()
    daily_fee = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        ordering = ("title", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(daily_fee__gte=Decimal("0.01")),
                name="book_daily_fee_positive",
            ),
        ]

    def __str__(self):
        return f"{self.title} by {self.author}"
