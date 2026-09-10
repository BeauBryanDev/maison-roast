
import threading

import numpy as np
from django.conf import settings
from PIL import Image

from .labels import UNKNOWN_LABEL, index_to_label

IMG_SIZE = 384

_session = None
_lock = threading.Lock()

# ONNX inference for the food classifier (MASTER_SPEC §8).

# Preprocessing must match training exactly, or predictions are quietly wrong:
# 384x384, bilinear
# float32 in [0, 255], NOT divided by 255 (EfficientNetV2 normalizes inside)
# NHWC layout, because the graph came from TensorFlow
# The graph already ends in softmax, hence iit never apply softmax again.

def get_session():
    """The ONNX session, created once and shared."""
    global _session
    
    if _session is None:
        
        with _lock:
            if _session is None:
                import onnxruntime as ort
                _session = ort.InferenceSession(
                    str(settings.BASIL_MODEL_PATH),
                    providers=['CPUExecutionProvider'],
                )
                
    return _session

# TENSORS = np.zeros((1, 384, 384, 3), dtype=np.float32)
def preprocess(image_file):
    """Image file to a (1, 384, 384, 3) float32 batch in [0, 255]."""
    with Image.open(image_file) as img:
        img = img.convert('RGB').resize((IMG_SIZE, IMG_SIZE), 
                                        Image.BILINEAR)
        
        # The model expects a batch of images, not a single image.
        array = np.asarray(img, dtype=np.float32)
        
    return array[np.newaxis, ...]


def predict(image_file, top_k=3):
    """Run the model. Returns (label, confidence, alternatives)."""
    session = get_session()
    input_name = session.get_inputs()[0].name

    # Already probabilities: the last Keras layer was Dense(softmax).
    probabilities = session.run(None, {input_name: preprocess(image_file)})[0][0]

    labels = index_to_label()
    order = np.argsort(probabilities)[::-1]

    top_index = int(order[0])
    top_label = labels[top_index]
    top_confidence = float(probabilities[top_index])

    # unknown is a real class but is never shown to the agent as an alternative.
    alternatives = [
        {'label': labels[int(i)], 'confidence': round(float(probabilities[i]), 4)}
        for i in order[1:]
        if labels[int(i)] != UNKNOWN_LABEL
    ][:top_k]

    return top_label, top_confidence, alternatives
