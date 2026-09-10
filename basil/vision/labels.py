
import json
from functools import lru_cache

from django.conf import settings

UNKNOWN_LABEL = 'unknown'

# Class labels for the food classifier.

@lru_cache(maxsize=1)
def index_to_label():
    """Ordered labels, index-aligned with the model output."""
    data = json.loads(settings.BASIL_LABEL_MAP_PATH.read_text())
    
    mapping = {int(k): v for k, v in data['index_to_class'].items()}
    
    return [mapping[i] for i in range(len(mapping))]


def label_for(index):
    
    labels = index_to_label()
    
    return labels[index] if 0 <= index < len(labels) else UNKNOWN_LABEL
