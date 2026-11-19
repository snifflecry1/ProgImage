from datetime import timedelta
from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.utils import timezone

from images.models import ImageData


@pytest.fixture
def media_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def make_record(*, status, age_minutes, with_file=False):
    image = ImageData.objects.create(
        content_type="image/png",
        size_bytes=4,
        status=status,
    )
    image.file.name = f"images/{image.id}.png"
    if with_file:
        image.file.storage.save(image.file.name, ContentFile(b"data"))
    # created_at is auto_now_add, so backdate it with an update.
    ImageData.objects.filter(pk=image.pk).update(
        file=image.file.name,
        created_at=timezone.now() - timedelta(minutes=age_minutes),
    )
    return image


def reconcile(**kwargs):
    out = StringIO()
    call_command("reconcile_images", stdout=out, **kwargs)
    return out.getvalue()


@pytest.mark.django_db
def test_stale_pending_with_file_is_failed_and_file_removed(media_storage):
    image = make_record(status=ImageData.Status.PENDING, age_minutes=30, with_file=True)

    output = reconcile()

    image.refresh_from_db()
    assert image.status == ImageData.Status.FAILED
    assert not (media_storage / image.file.name).exists()
    assert "Marked 1" in output


@pytest.mark.django_db
def test_stale_pending_without_file_is_failed(media_storage):
    image = make_record(status=ImageData.Status.PENDING, age_minutes=30)

    reconcile()

    image.refresh_from_db()
    assert image.status == ImageData.Status.FAILED


@pytest.mark.django_db
def test_recent_pending_and_other_statuses_are_untouched(media_storage):
    recent = make_record(status=ImageData.Status.PENDING, age_minutes=1, with_file=True)
    completed = make_record(
        status=ImageData.Status.COMPLETED, age_minutes=30, with_file=True
    )

    reconcile()

    recent.refresh_from_db()
    completed.refresh_from_db()
    assert recent.status == ImageData.Status.PENDING
    assert completed.status == ImageData.Status.COMPLETED
    assert (media_storage / recent.file.name).exists()
    assert (media_storage / completed.file.name).exists()


@pytest.mark.django_db
def test_dry_run_changes_nothing(media_storage):
    image = make_record(status=ImageData.Status.PENDING, age_minutes=30, with_file=True)

    output = reconcile(dry_run=True)

    image.refresh_from_db()
    assert image.status == ImageData.Status.PENDING
    assert (media_storage / image.file.name).exists()
    assert "1 stale pending upload(s) would be marked FAILED" in output


@pytest.mark.django_db
def test_older_than_must_be_positive():
    with pytest.raises(CommandError):
        reconcile(older_than=0)
