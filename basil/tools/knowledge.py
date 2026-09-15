
import voyageai

from basil.models import KnowledgeDocument
from basil.rag.retrieve import DEFAULT_TOP_K, search

# Knowledge base tool  
import logging
# Policies, brand story, allergens, recipes and coffee knowledge. 
# The caller is responsible for the user identity and the quantity. 
# The caller must be signed in to use this tool. 
logger = logging.getLogger(__name__)


def search_knowledge_base(query, top_k=DEFAULT_TOP_K):
    
    if not query or not str(query).strip():
        return {'error': 'Give me something to look up.'}

    if not KnowledgeDocument.objects.exists():
        return {'error': 'The knowledge base is empty. Run ingest_knowledge.'}

    try:
        results = search(str(query), top_k)
        
    except voyageai.error.RateLimitError:
        logger.exception('Knowledge lookup is rate limited right now.')
        # The free Voyage tier allows 3 requests a minute. Say so plainly
        # rather than letting Basil read it as "we have no such policy".
        return {'error': 'Knowledge lookup is rate limited right now. '
                         'Tell the customer to ask again in a moment.'}
        
    except Exception as exc:
        logger.exception('Knowledge lookup failed')
        return {'error': f'Knowledge lookup failed: {exc}'}

    payload = {'count': len(results), 'results': results}

    if not results:
        # Say "found nothing" explicitly. A bare empty list reads to the model
        # as "the shop has no such policy" -- same failure the rate-limit
        # branch above guards against.
        payload['note'] = ('Nothing in the knowledge base matched. Say you '
                           'could not find it rather than inventing an answer.')

    return payload