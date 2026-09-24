from django.contrib import admin

from .models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'kind', 'status', 'owner', 'size', 'created_at')
    list_filter = ('kind', 'status')
    search_fields = ('original_name', 'key', 'owner__username')
    readonly_fields = ('key', 'multipart_upload_id')
