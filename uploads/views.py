import math
import mimetypes
import os
import re
import uuid

from django.conf import settings
from django.core import signing
from django.http import (FileResponse, Http404, HttpResponse, HttpResponseRedirect,
                         StreamingHttpResponse)
from django.shortcuts import get_object_or_404
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MediaAsset
from .storage import ensure_bucket_cors, get_storage

ALLOWED_TYPES = {
    MediaAsset.Kind.VIDEO: {'video/mp4', 'video/webm', 'video/quicktime', 'video/x-m4v'},
    MediaAsset.Kind.IMAGE: {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif'},
}


def max_bytes(kind):
    return settings.MAX_VIDEO_BYTES if kind == MediaAsset.Kind.VIDEO else settings.MAX_IMAGE_BYTES


class MediaAssetSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MediaAsset
        fields = ['id', 'kind', 'status', 'original_name', 'content_type', 'size',
                  'duration_seconds', 'created_at', 'url']

    def get_url(self, obj):
        return obj.public_url() if obj.kind == MediaAsset.Kind.IMAGE and obj.is_ready else None


class UploadInitSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=MediaAsset.Kind.choices)
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)
    size = serializers.IntegerField(min_value=1)

    def validate(self, data):
        kind = data['kind']
        if data['content_type'] not in ALLOWED_TYPES[kind]:
            raise serializers.ValidationError(
                {'content_type': f"Unsupported {kind} type. Allowed: "
                                 f"{', '.join(sorted(ALLOWED_TYPES[kind]))}"})
        limit = max_bytes(kind)
        if data['size'] > limit:
            raise serializers.ValidationError(
                {'size': f'File is too large (max {limit // (1024 * 1024)} MB).'})
        request = self.context['request']
        if kind == MediaAsset.Kind.VIDEO and not hasattr(request.user, 'teacher'):
            raise serializers.ValidationError('Only teachers can upload videos.')
        return data


def build_key(user, kind, filename):
    stem, ext = os.path.splitext(get_valid_filename(filename) or 'file')
    ext = ext.lower()[:10] or mimetypes.guess_extension('video/mp4' if kind == 'video' else 'image/jpeg')
    return f'{kind}s/{user.pk}/{uuid.uuid4().hex}/{stem[:80]}{ext}'


class UploadInitView(APIView):
    """Step 1: reserve an object key and hand back presigned upload URL(s)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UploadInitSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        storage = get_storage()
        ensure_bucket_cors()

        asset = MediaAsset(
            owner=request.user,
            kind=data['kind'],
            key=build_key(request.user, data['kind'], data['filename']),
            original_name=data['filename'][:255],
            content_type=data['content_type'],
            size=data['size'],
        )
        payload = {}
        if storage.supports_multipart and data['size'] > settings.MULTIPART_THRESHOLD:
            asset.multipart_upload_id = storage.create_multipart(asset.key, asset.content_type)
            part_size = settings.MULTIPART_PART_SIZE
            payload.update(strategy='multipart', part_size=part_size,
                           part_count=math.ceil(data['size'] / part_size))
        else:
            payload.update(strategy='single',
                           upload_url=storage.presign_put(asset.key, asset.content_type),
                           headers={'Content-Type': asset.content_type})
        asset.save()
        payload['asset'] = MediaAssetSerializer(asset).data
        return Response(payload, status=status.HTTP_201_CREATED)


def owned_pending_asset(request, pk):
    return get_object_or_404(MediaAsset, pk=pk, owner=request.user,
                             status=MediaAsset.Status.PENDING)


class UploadPartsView(APIView):
    """Step 2 (multipart only): presign a batch of part URLs."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        asset = owned_pending_asset(request, pk)
        if not asset.multipart_upload_id:
            return Response({'detail': 'Not a multipart upload.'}, status=400)
        numbers = request.data.get('part_numbers') or []
        if not isinstance(numbers, list) or not numbers or len(numbers) > 100:
            return Response({'detail': 'Send 1-100 part_numbers.'}, status=400)
        storage = get_storage()
        urls = {}
        for n in numbers:
            n = int(n)
            if not 1 <= n <= 10000:
                return Response({'detail': 'Part numbers must be 1-10000.'}, status=400)
            urls[n] = storage.presign_part(asset.key, asset.multipart_upload_id, n)
        return Response({'urls': urls})


class UploadCompleteView(APIView):
    """Step 3: confirm the bytes landed and mark the asset ready."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        asset = owned_pending_asset(request, pk)
        storage = get_storage()
        if asset.multipart_upload_id:
            parts = request.data.get('parts') or []
            if not parts:
                return Response({'detail': 'parts are required.'}, status=400)
            storage.complete_multipart(asset.key, asset.multipart_upload_id, parts)
            asset.multipart_upload_id = ''

        size = storage.object_size(asset.key)
        if size is None:
            return Response({'detail': 'Upload not found in storage yet.'}, status=409)
        if size > max_bytes(asset.kind):
            storage.delete(asset.key)
            asset.status = MediaAsset.Status.FAILED
            asset.save()
            return Response({'detail': 'File exceeds the size limit.'}, status=400)

        duration = request.data.get('duration_seconds')
        if duration not in (None, ''):
            asset.duration_seconds = max(0, int(float(duration)))
        asset.size = size
        asset.status = MediaAsset.Status.READY
        asset.save()
        return Response(MediaAssetSerializer(asset).data)


class UploadAbortView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        asset = owned_pending_asset(request, pk)
        storage = get_storage()
        if asset.multipart_upload_id:
            storage.abort_multipart(asset.key, asset.multipart_upload_id)
        else:
            storage.delete(asset.key)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def media_redirect(request, pk):
    """Public, cacheable entry point for images (covers, avatars).

    Videos are never exposed here; they go through the access-checked
    lesson stream endpoint.
    """
    asset = get_object_or_404(MediaAsset, pk=pk, kind=MediaAsset.Kind.IMAGE,
                              status=MediaAsset.Status.READY)
    response = HttpResponseRedirect(get_storage().presign_get(asset.key, expires=3600))
    response['Cache-Control'] = 'public, max-age=600'
    return response


# ---------------------------------------------------------------------------
# Local filesystem stand-ins for presigned URLs (development only)
# ---------------------------------------------------------------------------

def _local_key(request, op):
    storage = get_storage()
    if storage.name != 'local':
        raise Http404
    try:
        return storage, storage.verify(request.GET.get('token', ''),
                                       request.GET.get('ttl', 3600), op)
    except (signing.BadSignature, ValueError):
        raise Http404


def _cors(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, HEAD, PUT, OPTIONS'
    response['Access-Control-Allow-Headers'] = '*'
    response['Access-Control-Expose-Headers'] = 'ETag, Content-Length, Content-Range, Accept-Ranges'
    return response


@csrf_exempt
@require_http_methods(['PUT', 'OPTIONS'])
def local_object_put(request):
    if request.method == 'OPTIONS':
        return _cors(HttpResponse())
    storage, key = _local_key(request, 'put')
    path = storage.path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as fh:
        while chunk := request.read(1024 * 1024):
            fh.write(chunk)
    response = _cors(HttpResponse(status=200))
    response['ETag'] = f'"{uuid.uuid4().hex}"'
    return response


RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)')


@require_http_methods(['GET', 'HEAD', 'OPTIONS'])
def local_object_get(request):
    if request.method == 'OPTIONS':
        return _cors(HttpResponse())
    storage, key = _local_key(request, 'get')
    path = storage.path_for(key)
    if not path.exists():
        raise Http404
    size = path.stat().st_size
    content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    match = RANGE_RE.match(request.headers.get('Range', ''))
    if not match or not (match.group(1) or match.group(2)):
        response = FileResponse(open(path, 'rb'), content_type=content_type)
        response['Accept-Ranges'] = 'bytes'
        return _cors(response)

    start, end = match.groups()
    if start:
        start, end = int(start), min(int(end) if end else size - 1, size - 1)
    else:  # suffix range: last N bytes
        start, end = max(size - int(end), 0), size - 1
    if start >= size or start > end:
        response = HttpResponse(status=416)
        response['Content-Range'] = f'bytes */{size}'
        return _cors(response)

    def stream():
        remaining = end - start + 1
        with open(path, 'rb') as fh:
            fh.seek(start)
            while remaining > 0:
                chunk = fh.read(min(512 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    response = StreamingHttpResponse(stream(), status=206, content_type=content_type)
    response['Content-Range'] = f'bytes {start}-{end}/{size}'
    response['Content-Length'] = str(end - start + 1)
    response['Accept-Ranges'] = 'bytes'
    return _cors(response)
