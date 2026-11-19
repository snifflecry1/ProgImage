from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from images.models import ImageData
from images.services import cleanup_failed_upload


class Command(BaseCommand):
    help = "Mark stale PENDING uploads as FAILED and delete any written files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than",
            type=int,
            default=15,
            help="Minutes since creation before a PENDING upload is stale "
            "(default: 15).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report stale uploads without changing anything.",
        )

    def handle(self, *args, older_than, dry_run, **options):
        # A very small window could fail uploads that are still in progress.
        if older_than < 1:
            raise CommandError("--older-than must be at least 1 minute.")

        cutoff = timezone.now() - timedelta(minutes=older_than)
        stale = ImageData.objects.filter(
            status=ImageData.Status.PENDING,
            created_at__lt=cutoff,
        ).order_by("created_at")

        if dry_run:
            self.stdout.write(
                f"{stale.count()} stale pending upload(s) would be marked FAILED."
            )
            return

        failed = sum(
            cleanup_failed_upload(image, image.file.storage)
            for image in stale.iterator()
        )
        self.stdout.write(
            self.style.SUCCESS(f"Marked {failed} stale pending upload(s) as FAILED.")
        )
