from django.conf import settings
from django.core.management.base import BaseCommand

from uploads.storage import get_storage


class Command(BaseCommand):
    help = 'Allow the frontend to upload to and stream from the object storage bucket.'

    def add_arguments(self, parser):
        parser.add_argument('origins', nargs='*', help='Defaults to CORS_ALLOWED_ORIGINS.')

    def handle(self, *args, origins, **options):
        storage = get_storage()
        if storage.name != 's3':
            self.stdout.write('Local storage in use; nothing to configure.')
            return
        origins = origins or settings.CORS_ALLOWED_ORIGINS
        storage.configure_cors(origins)
        self.stdout.write(self.style.SUCCESS(
            f'CORS configured on {storage.bucket} for: {", ".join(origins)}'))
