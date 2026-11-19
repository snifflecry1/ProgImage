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
    # This query protects against race conditions
    updated = ImageData.objects.filter(
        pk=image_id,
        status=ImageData.Status.PENDING,
    ).update(
        status=ImageData.Status.COMPLETED,
        updated_at=timezone.now(),
    )
    if updated != 1:
        raise RuntimeError(f"Could not mark image {image_id} as completed")


def mark_image_failed(image_id) -> bool:
    """Move a PENDING image to FAILED. Returns True if this call changed it."""
    updated = ImageData.objects.filter(
        pk=image_id,
        status=ImageData.Status.PENDING,
    ).update(
        status=ImageData.Status.FAILED,
        updated_at=timezone.now(),
    )
    return updated == 1


def cleanup_failed_upload(image: ImageData, storage: Storage) -> bool:
    """
    Best-effort: mark a PENDING upload FAILED and delete its file.
    Returns True if this call marked it FAILED.
    """
    marked_failed = False
    try:
        # Only delete the file if this call moved the row to FAILED, so a
        # COMPLETED record never loses its file.
        marked_failed = mark_image_failed(image.id)
        if marked_failed:
            storage.delete(image.file.name)
    except Exception:
        logger.exception(
            "Cleanup failed for image image_id=%s",
            image.id,
            extra={"image_id": str(image.id)},
        )
    return marked_failed


def create_image(
    uploaded_file,
    *,
    content_type: str,
    extension: str,
) -> ImageData:
    try:
        image = create_pending_image(
            uploaded_file,
            content_type=content_type,
            extension=extension,
        )
    except Exception:
        logger.exception("Could not create pending image record")
        raise

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
            "Image upload failed image_id=%s",
            image.id,
            extra={"image_id": str(image.id)},
        )
        cleanup_failed_upload(image, storage)
        raise

    image.status = ImageData.Status.COMPLETED
    return image
