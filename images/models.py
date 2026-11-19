import uuid

from django.db import models


class ImageData(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    file = models.FileField(
        upload_to="images/",
        max_length=500,
        blank=True,
    )
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="images_status_created_idx",
            ),
        ]

    def __str__(self):
        return str(self.id)
