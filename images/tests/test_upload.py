from io import BytesIO
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from images.models import ImageData
from images.serializers import MAX_FILE_SIZE, ImageUploadSerializer
from images.services import mark_image_failed

UPLOAD_FAILED = {"detail": "The image could not be stored. Please retry."}


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def media_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def make_image(*, image_format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (100, 100), "red").save(buffer, format=image_format)

    return SimpleUploadedFile(
        "test-image.png",
        buffer.getvalue(),
        content_type="image/png",
    )


@pytest.mark.django_db
def test_upload_image_successfully(client, media_storage):
    response = client.post(
        reverse("image-upload"),
        {"file": make_image()},
        format="multipart",
    )

    assert response.status_code == 201

    image_id = UUID(response.data["id"])
    image = ImageData.objects.get(pk=image_id)

    assert image.status == ImageData.Status.COMPLETED
    assert image.content_type == "image/png"
    assert image.size_bytes > 0
    assert image.file.name == f"images/{image_id}.png"

    stored_file = media_storage / image.file.name
    assert stored_file.is_file()

    with Image.open(stored_file) as stored_image:
        assert stored_image.format == "PNG"
        assert stored_image.size == (100, 100)


@pytest.mark.django_db
def test_upload_without_file_returns_400(client, media_storage):
    response = client.post(
        reverse("image-upload"),
        {},
        format="multipart",
    )

    assert response.status_code == 400
    assert "file" in response.data
    assert ImageData.objects.count() == 0


@pytest.mark.django_db
def test_upload_invalid_image_returns_400(client, media_storage):
    invalid_file = SimpleUploadedFile(
        "invalid.png",
        b"this is not an image",
        content_type="image/png",
    )

    response = client.post(
        reverse("image-upload"),
        {"file": invalid_file},
        format="multipart",
    )

    assert response.status_code == 400
    assert "file" in response.data
    assert ImageData.objects.count() == 0


@pytest.mark.django_db
def test_upload_unsupported_format_returns_400(client, media_storage):
    buffer = BytesIO()
    Image.new("RGB", (100, 100), "red").save(buffer, format="GIF")

    gif_file = SimpleUploadedFile(
        "test.gif",
        buffer.getvalue(),
        content_type="image/gif",
    )

    response = client.post(
        reverse("image-upload"),
        {"file": gif_file},
        format="multipart",
    )

    assert response.status_code == 400
    assert "file" in response.data
    assert ImageData.objects.count() == 0


@pytest.mark.django_db
def test_storage_failure_marks_image_failed(client, media_storage):
    with patch(
        "django.core.files.storage.FileSystemStorage._save",
        side_effect=OSError("Disk write failed"),
    ):
        response = client.post(
            reverse("image-upload"), {"file": make_image()}, format="multipart"
        )

    assert response.status_code == 503
    assert response.data == UPLOAD_FAILED

    image = ImageData.objects.get()
    assert image.status == ImageData.Status.FAILED
    assert not (media_storage / image.file.name).exists()


@pytest.mark.django_db
def test_completion_failure_marks_failed_and_removes_file(client, media_storage):
    with patch(
        "images.services.mark_image_completed",
        side_effect=RuntimeError("DB update failed"),
    ):
        response = client.post(
            reverse("image-upload"), {"file": make_image()}, format="multipart"
        )

    assert response.status_code == 503

    image = ImageData.objects.get()
    assert image.status == ImageData.Status.FAILED
    assert not (media_storage / image.file.name).exists()


@pytest.mark.django_db
def test_cleanup_db_error_keeps_pending_and_file(client, media_storage):
    with (
        patch(
            "images.services.mark_image_completed",
            side_effect=RuntimeError("DB update failed"),
        ),
        patch(
            "images.services.mark_image_failed",
            side_effect=RuntimeError("DB unavailable"),
        ),
    ):
        response = client.post(
            reverse("image-upload"), {"file": make_image()}, format="multipart"
        )

    assert response.status_code == 503

    image = ImageData.objects.get()
    assert image.status == ImageData.Status.PENDING
    assert (media_storage / image.file.name).exists()


@pytest.mark.django_db
def test_record_creation_failure_returns_503(client, media_storage):
    with patch(
        "images.services.create_pending_image",
        side_effect=RuntimeError("DB unavailable"),
    ):
        response = client.post(
            reverse("image-upload"), {"file": make_image()}, format="multipart"
        )

    assert response.status_code == 503
    assert ImageData.objects.count() == 0


@pytest.mark.django_db
def test_mark_image_failed_does_not_override_completed():
    image = ImageData.objects.create(
        content_type="image/png",
        size_bytes=1,
        status=ImageData.Status.COMPLETED,
    )

    assert mark_image_failed(image.id) is False
    image.refresh_from_db()
    assert image.status == ImageData.Status.COMPLETED


def test_rejects_file_over_size_limit():
    uploaded_file = Mock(size=MAX_FILE_SIZE + 1)

    serializer = ImageUploadSerializer()

    with pytest.raises(ValidationError):
        serializer.validate_file(uploaded_file)
