from django.contrib import admin

from .models import ChatMessage, ChatSession, UploadedImage


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('id', 'session_key', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    list_select_related = ('user',)
    inlines = [ChatMessageInline]


@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'image', 'created_at')
    readonly_fields = ('id', 'created_at')
    list_select_related = ('session',)
