from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from borrowings.models import Borrowing


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"

    class PaymentType(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        FINE = "FINE", "Fine"

    status = models.CharField(max_length=7, choices=Status.choices)
    type = models.CharField(max_length=7, choices=PaymentType.choices)
    borrowing = models.ForeignKey(
        Borrowing,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    session_url = models.URLField()
    session_id = models.CharField(max_length=255, unique=True)
    money_to_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        ordering = ("-id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(money_to_pay__gte=Decimal("0.01")),
                name="payment_money_to_pay_positive",
            ),
        ]

    def __str__(self):
        return f"{self.get_type_display()} for borrowing {self.borrowing_id}"
