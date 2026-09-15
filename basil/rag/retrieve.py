
import voyageai
from django.conf import settings
from pgvector.django import CosineDistance

from basil.models import KnowledgeDocument

DEFAULT_TOP_K = 4
MAX_TOP_K = 10

_client = None


class KnowledgeSearchError(Exception):
    """Raised when the embeddings backend fails. Distinct from a clean
    zero-result search, so callers can tell the two apart."""
    pass

# Semantic Retrieval API

def get_client():
    
    global _client
    
    if _client is None:
        
        if not settings.VOYAGE_API_KEY:
            
            raise RuntimeError('VOYAGE_API_KEY is not set.')
        
        _client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
        
    return _client


def embed_query(text):
    """input_type=query, not document -- Voyage embeds the two asymmetrically
    and using the wrong one costs retrieval accuracy."""
    result = get_client().embed(
        [text],
        model=settings.VOYAGE_MODEL, 
        input_type='query')
    
    return result.embeddings[0]


def search(query, top_k=DEFAULT_TOP_K):
    """Nearest chunks by cosine distance. Returns [{text, source, similarity}]."""
    try:
        top_k = max(1, min(int(top_k), MAX_TOP_K))
        
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K
        
        
    try:
        
        query = embed_query(query)
        
    except voyageai.error.RateLimitError:
        
        raise KnowledgeSearchError('rate limited')

    rows = (
        KnowledgeDocument.objects
        .annotate(distance=CosineDistance('embedding', embed_query(query)))
        .order_by('distance')[:top_k]
    )

    return [{
        'text': row.content,
        'source': row.source,
        'heading': row.metadata.get('heading', ''),
        'similarity': round(1 - float(row.distance), 4),
        
    } for row in rows]
