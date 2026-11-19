import logging

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.cache import patch_cache_control
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImageData
from .serializers import ImageUploadSerializer
from .services import create_image

logger = logging.getLogger(__name__)

IMAGE_CACHE_MAX_AGE = 60 * 60 * 24 * 365  # one year, in seconds


class ImageUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            image = create_image(
                serializer.validated_data["file"],
                content_type=serializer.validated_data["content_type"],
                extension=serializer.validated_data["extension"],
            )
        except Exception:
            # Logged and cleaned up in create_image.
            return Response(
                {"detail": "The image could not be stored. Please retry."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"id": str(image.id)},
            status=status.HTTP_201_CREATED,
        )


class ImageRetrieveView(APIView):
    def get(self, request, image_id):
        image = get_object_or_404(
            ImageData,
            pk=image_id,
            status=ImageData.Status.COMPLETED,
        )

        try:
            file = image.file.open("rb")
        except FileNotFoundError:
            logger.warning(
                "Completed image file missing image_id=%s",
                image.id,
                extra={"image_id": str(image.id)},
            )
            raise Http404("Image file not found")

        response = FileResponse(
            file,
            content_type=image.content_type,
        )
        # A completed image never changes for its UUID, so clients and CDNs
        # can cache it for a year without revalidating.
        patch_cache_control(
            response,
            public=True,
            max_age=IMAGE_CACHE_MAX_AGE,
            immutable=True,
        )
        return response
