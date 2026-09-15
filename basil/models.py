
import uuid

from django.conf import settings
from django.db import models
from products.models import Product

from pgvector.django import HnswIndex, VectorField

# Basil Inner Models
class ChatSessionQuerySet(models.QuerySet):
    
    def for_request(self, request):
        """Sessions the caller may see. The only supported lookup."""
        if request.user.is_authenticated:
            return self.filter(user=request.user)

        session_key = request.session.session_key
        
        if not session_key:
            return self.none()
        
        return self.filter(user__isnull=True, 
                           session_key=session_key)


class ChatSession(models.Model):
    
    id = models.UUIDField(primary_key=True, 
                          default=uuid.uuid4, 
                          editable=False)

    # Null for anonymous visitors, who are matched by session_key instead.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    session_key = models.CharField(max_length=40, 
                                   blank=True,
                                   db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ChatSessionQuerySet.as_manager()

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['user', '-updated_at'])]

    def __str__(self):
        who = self.user.username if self.user else f'anon:{self.session_key[:8]}'
        return f'ChatSession {self.id} ({who})'


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'
        TOOL_USE = 'tool_use', 'Tool use'
        TOOL_RESULT = 'tool_result', 'Tool result'

    session = models.ForeignKey(
        ChatSession, 
        on_delete=models.CASCADE, 
        related_name='messages',
    )
    role = models.CharField(max_length=16, 
                            choices=Role.choices)
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # id breaks timestamp ties; out-of-order replay corrupts the history.
        ordering = ['created_at', 'id']
        indexes = [models.Index(fields=['session', 'created_at'])]

    def __str__(self):
        return f'{self.role} @ {self.created_at:%Y-%m-%d %H:%M:%S}'


class UploadedImage(models.Model):
    
    id = models.UUIDField(primary_key=True, 
                          default=uuid.uuid4,
                          editable=False)
    
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE, 
        related_name='images',
    )
 
    image = models.FileField(upload_to=f'{settings.BASIL_UPLOAD_DIR}/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'UploadedImage {self.id}'


class KnowledgeDocument(models.Model):
    """One embedded chunk of the RAG corpus """

    source = models.CharField(max_length=255, db_index=True)
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()

    # 1024 measured from a live voyage-4-lite response.
    embedding = VectorField(dimensions=settings.VOYAGE_DIM)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['source', 'chunk_index']
        # Re-ingesting updates rows in place instead of duplicating them (§7).
        constraints = [
            models.UniqueConstraint(fields=['source', 'chunk_index'],
                                    name='unique_chunk_per_source'),
        ]
        indexes = [
            HnswIndex(name='knowledge_embedding_hnsw',
                      fields=['embedding'],
                      m=16,
                      ef_construction=64,
                      opclasses=['vector_cosine_ops']),
        ]

    def __str__(self):
        return f'{self.source} #{self.chunk_index}'



class NutritionInfo(models.Model):
    """Nutrition data for one menu item, keyed by CNN vision label.
    vision label is the connection between the 40 CNN classes and the
    menus items. It is not the same as the USDA fdcId.
    """
    #fdc_id = models.PositiveIntegerField()
    
    vision_label = models.CharField(max_length=64, 
                                    unique=True, 
                                    db_index=True)
    product = models.ForeignKey(
        Product, null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='nutrition_info',
    )
 
    basis_g = models.PositiveIntegerField(
        default=100,
        help_text='Gram basis these values are reported for (100 for all rows today).',
    )
    calories_kcal = models.FloatField(null=True, blank=True)
    protein_g = models.FloatField(null=True, blank=True)
    carbs_g = models.FloatField(null=True, blank=True)
    fat_g = models.FloatField(null=True, blank=True)
 
    # Provenance, kept for traceability back to the USDA lookup.
    description = models.CharField(max_length=255, blank=True)
    data_type = models.CharField(max_length=64, blank=True)
    fdc_id = models.PositiveIntegerField(null=True, blank=True)
    source_file = models.CharField(max_length=64, blank=True)
 
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['vision_label']
 
    def __str__(self):
        return f'NutritionInfo({self.vision_label})'
 