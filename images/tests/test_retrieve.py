from uuid import uuid4

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from rest_framework.test import APIClient

from images.models import ImageData


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def media_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.mark.django_db
def test_retrieve_completed_image(client, media_storage):
    image = ImageData.objects.create(
        content_type="image/png",
        size_bytes=12,
        status=ImageData.Status.COMPLETED,
    )
    image.file.save("test.png", ContentFile(b"test content"))

    response = client.get(reverse("image-detail", kwargs={"image_id": image.id}))

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert b"".join(response.streaming_content) == b"test content"


@pytest.mark.django_db
def test_retrieve_unknown_image_returns_404(client, media_storage):
    response = client.get(reverse("image-detail", kwargs={"image_id": uuid4()}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_pending_image_returns_404(client, media_storage):
    image = ImageData.objects.create(
        content_type="image/png",
        size_bytes=12,
        status=ImageData.Status.PENDING,
    )

    response = client.get(reverse("image-detail", kwargs={"image_id": image.id}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_missing_file_returns_404(client, media_storage):
    image = ImageData.objects.create(
        content_type="image/png",
        size_bytes=12,
        status=ImageData.Status.COMPLETED,
    )
    image.file.name = f"images/{image.id}.png"
    image.save(update_fields=["file"])

    response = client.get(reverse("image-detail", kwargs={"image_id": image.id}))

    assert response.status_code == 404
