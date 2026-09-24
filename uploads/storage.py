"""Object storage backends.

`S3Storage` talks to Neon Object Storage (any S3-compatible service works).
`LocalStorage` mimics the same presigned-URL contract against the local disk,
so the whole upload/stream flow can be developed and tested offline.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.urls import reverse


class S3Storage:
    name = 's3'
    supports_multipart = True

    def __init__(self):
        import boto3
        from botocore.config import Config

        self.bucket = settings.STORAGE_BUCKET
        self.client = boto3.client(
            's3',
            endpoint_url=settings.AWS_ENDPOINT_URL_S3,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        )

    def presign_put(self, key, content_type, expires=3600):
        return self.client.generate_presigned_url(
            'put_object',
            Params={'Bucket': self.bucket, 'Key': key, 'ContentType': content_type},
            ExpiresIn=expires,
        )

    def presign_get(self, key, expires=3600, download_name=None):
        params = {'Bucket': self.bucket, 'Key': key}
        if download_name:
            params['ResponseContentDisposition'] = (
                f"inline; filename*=UTF-8''{quote(download_name)}")
        return self.client.generate_presigned_url('get_object', Params=params, ExpiresIn=expires)

    def create_multipart(self, key, content_type):
        response = self.client.create_multipart_upload(
            Bucket=self.bucket, Key=key, ContentType=content_type)
        return response['UploadId']

    def presign_part(self, key, upload_id, part_number, expires=3600):
        return self.client.generate_presigned_url(
            'upload_part',
            Params={'Bucket': self.bucket, 'Key': key,
                    'UploadId': upload_id, 'PartNumber': part_number},
            ExpiresIn=expires,
        )

    def complete_multipart(self, key, upload_id, parts):
        self.client.complete_multipart_upload(
            Bucket=self.bucket, Key=key, UploadId=upload_id,
            MultipartUpload={'Parts': [
                {'ETag': p['etag'], 'PartNumber': int(p['part_number'])}
                for p in sorted(parts, key=lambda p: int(p['part_number']))
            ]},
        )

    def abort_multipart(self, key, upload_id):
        self.client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)

    def object_size(self, key):
        """Size in bytes, or None when the object does not exist."""
        from botocore.exceptions import ClientError
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key)['ContentLength']
        except ClientError:
            return None

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def configure_cors(self, origins):
        self.client.put_bucket_cors(Bucket=self.bucket, CORSConfiguration={'CORSRules': [{
            'AllowedOrigins': origins,
            'AllowedMethods': ['GET', 'HEAD', 'PUT'],
            'AllowedHeaders': ['*'],
            # ETag is needed to complete multipart uploads from the browser;
            # the range headers let <video> seek.
            'ExposeHeaders': ['ETag', 'Content-Length', 'Content-Range', 'Accept-Ranges'],
            'MaxAgeSeconds': 3600,
        }]})


class LocalStorage:
    """Filesystem stand-in that issues signed backend URLs instead of S3 URLs."""

    name = 'local'
    supports_multipart = False
    salt = 'uploads.local'

    def __init__(self):
        self.root = Path(settings.LOCAL_STORAGE_ROOT)

    def path_for(self, key):
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError('Invalid object key')
        return path

    def _url(self, route, key, expires, **extra):
        token = signing.dumps({'key': key, **extra}, salt=self.salt)
        return f"{settings.BACKEND_URL}{reverse(route)}?token={token}&ttl={expires}"

    def presign_put(self, key, content_type, expires=3600):
        return self._url('local-object-put', key, expires, op='put')

    def presign_get(self, key, expires=3600, download_name=None):
        return self._url('local-object-get', key, expires, op='get')

    def verify(self, token, ttl, op):
        data = signing.loads(token, salt=self.salt, max_age=int(ttl))
        if data.get('op') != op:
            raise signing.BadSignature('Wrong operation')
        return data['key']

    def object_size(self, key):
        path = self.path_for(key)
        return path.stat().st_size if path.exists() else None

    def delete(self, key):
        path = self.path_for(key)
        if path.exists():
            path.unlink()

    def configure_cors(self, origins):
        return None


_cors_applied = False


def ensure_bucket_cors():
    """Idempotently allow the frontend origins to upload to the bucket."""
    global _cors_applied
    if _cors_applied or not settings.STORAGE_AUTO_CORS:
        return
    storage = get_storage()
    if storage.name == 's3':
        origins = list(settings.CORS_ALLOWED_ORIGINS)
        if settings.CORS_ALLOWED_ORIGIN_REGEXES:
            # S3 CORS has no regex support; allow any origin for PUT/GET when
            # preview deployments are enabled. URLs are presigned regardless.
            origins = ['*']
        storage.configure_cors(origins)
    _cors_applied = True


@lru_cache(maxsize=1)
def get_storage():
    if settings.STORAGE_BACKEND == 's3':
        return S3Storage()
    return LocalStorage()
