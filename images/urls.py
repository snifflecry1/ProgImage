from django.urls import path

from .views import ImageRetrieveView, ImageUploadView

urlpatterns = [
    path("", ImageUploadView.as_view(), name="image-upload"),
    path("<uuid:image_id>/", ImageRetrieveView.as_view(), name="image-detail"),
]
