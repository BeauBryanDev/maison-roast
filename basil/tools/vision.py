
from django.conf import settings

from basil.models import UploadedImage
from basil.vision.infer import predict
from basil.vision.labels import UNKNOWN_LABEL

#  Visisn API
# Returns what the classifier saw. 
# The classifier is trained to identify coffee, pastries, and other foods.
# It is not trained to identify people, places, or things just 40 types of food.

def vision_identify(image_id, session=None):
    """Returns a prediction and alternatives."""
    try:
        images = UploadedImage.objects.all()
        
        if session is not None:
            
            images = images.filter(session=session)
            
        image = images.get(pk=image_id)
        
    except (UploadedImage.DoesNotExist, ValueError, TypeError):
        return {'error': f'No uploaded image with id {image_id}.'}

    try:
        with image.image.open('rb') as handle:
            label, confidence, alternatives = predict(handle)
            
    except FileNotFoundError:
        return {'error': 'That image is no longer available.'}
    
    except Exception as exc:
        return {'error': f'Could not read that image: {exc}'}

    is_unknown = (
        label == UNKNOWN_LABEL or confidence < settings.BASIL_UNKNOWN_THRESHOLD
    )

    return {
        'prediction': {'label': label, 'confidence': round(confidence, 4)},
        'alternatives': alternatives,
        'is_unknown': is_unknown,
    }
