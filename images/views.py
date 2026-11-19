import logging

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImageData
from .serializers import ImageUploadSerializer
from .services import create_image

logger = logging.getLogger(__name__)


class ImageUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image = create_image(
            serializer.validated_data["file"],
            content_type=serializer.validated_data["content_type"],
            extension=serializer.validated_data["extension"],
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
                "Completed image file missing",
                extra={"image_id": str(image.id)},
            )
            raise Http404("Image file not found")

        return FileResponse(
            file,
            content_type=image.content_type,
        )
