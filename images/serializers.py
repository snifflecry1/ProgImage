from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from rest_framework import serializers

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000

PillowImage.MAX_IMAGE_PIXELS = MAX_PIXELS
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class ImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=False)

    def validate_file(self, uploaded_file):
        if uploaded_file.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                "Image exceeds the 10 MiB upload limit.",
                code="file_too_large",
            )

        try:
            with PillowImage.open(uploaded_file) as image:
                image_format = image.format
                width, height = image.size

                if width * height > MAX_PIXELS:
                    raise serializers.ValidationError(
                        "Image exceeds the 25-megapixel limit."
                    )

                if image_format not in ALLOWED_FORMATS:
                    raise serializers.ValidationError(
                        "Only JPEG, PNG and WebP images are supported."
                    )

                image.verify()

        except PillowImage.DecompressionBombError:
            raise serializers.ValidationError(
                "Image dimensions exceed the permitted limit."
            )
        except (UnidentifiedImageError, OSError, ValueError):
            raise serializers.ValidationError("The uploaded file is not a valid image.")
        finally:
            uploaded_file.seek(0)

        self._validated_format = image_format
        return uploaded_file

    def validate(self, attrs):
        content_type, extension = ALLOWED_FORMATS[self._validated_format]
        attrs["content_type"] = content_type
        attrs["extension"] = extension

        return attrs
