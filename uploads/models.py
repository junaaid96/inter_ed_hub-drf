import uuid

from django.conf import settings
from django.db import models


class MediaAsset(models.Model):
    """A file living in object storage (Neon Object Storage in production).

    Bytes never pass through Django: the browser uploads straight to the
    bucket with presigned URLs, and players stream from presigned GET URLs.
    """

    class Kind(models.TextChoices):
        VIDEO = 'video', 'Video'
        IMAGE = 'image', 'Image'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending upload'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='media_assets')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    key = models.CharField(max_length=512, unique=True)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100)
    size = models.BigIntegerField(default=0)
    # Filled for in-flight multipart uploads only.
    multipart_upload_id = models.CharField(max_length=512, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['owner', 'status'])]

    def __str__(self):
        return f'{self.kind}:{self.original_name or self.key}'

    @property
    def is_ready(self):
        return self.status == self.Status.READY

    def public_url(self):
        """Stable API URL that redirects to a fresh presigned GET (images)."""
        return f'{settings.BACKEND_URL}/media/{self.id}/'
