# images/services.py

import logging

from django.core.files.storage import Storage
from django.utils import timezone

from .models import ImageData

logger = logging.getLogger(__name__)


def create_pending_image(
    uploaded_file,
    *,
    content_type: str,
    extension: str,
) -> ImageData:
    image = ImageData(
        content_type=content_type,
        size_bytes=uploaded_file.size,
        status=ImageData.Status.PENDING,
    )

    image.file.name = f"images/{image.id}{extension}"
    image.save(force_insert=True)

    return image


def store_image(
    image: ImageData,
    uploaded_file,
    *,
    storage: Storage,
) -> str:
    uploaded_file.seek(0)
    return storage.save(image.file.name, uploaded_file)


def mark_image_completed(image_id) -> None:
    updated = ImageData.objects.filter(
        pk=image_id,
        status=ImageData.Status.PENDING,
    ).update(
        status=ImageData.Status.COMPLETED,
        updated_at=timezone.now(),
    )
    if updated != 1:
        raise RuntimeError(f"Could not mark image {image_id} as completed")


def create_image(
    uploaded_file,
    *,
    content_type: str,
    extension: str,
) -> ImageData:
    image = create_pending_image(
        uploaded_file,
        content_type=content_type,
        extension=extension,
    )

    storage = image.file.storage

    try:
        saved_key = store_image(
            image,
            uploaded_file,
            storage=storage,
        )

        if saved_key != image.file.name:
            raise ValueError("Storage returned an unexpected filename")

        mark_image_completed(image.id)

    except Exception:
        logger.exception(
            "Image upload failed",
            extra={"image_id": str(image.id)},
        )
        raise

    image.status = ImageData.Status.COMPLETED
    return image
