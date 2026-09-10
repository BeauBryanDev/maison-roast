
import json
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, UnidentifiedImageError

from .agent import run_turn
from .models import ChatMessage, ChatSession, UploadedImage

ALLOWED_TYPES = {'image/jpeg', 'image/png'}
ALLOWED_FORMATS = {'JPEG', 'PNG'}

# How an uploaded photo is named to the model. Written by chat(), read back by
# history() -- one definition so the two cannot drift apart.
IMAGE_MARKER = '[The customer uploaded a photo. image_id: {image_id}]'
IMAGE_MARKER_RE = re.compile(
    r'^\[The customer uploaded a photo\. image_id: ([0-9a-fA-F-]+)\]\n?')

# Enough to restore a conversation without sending a year of history to the rail.
HISTORY_LIMIT = 60

# Basil HTTP endpoints.

def get_or_create_session(request):
    """The caller's current chat session, creating one if needed."""
    session = ChatSession.objects.for_request(request).first()
    if session is not None:
        return session

    if request.user.is_authenticated:
        return ChatSession.objects.create(user=request.user)

    if not request.session.session_key:
        request.session.create()
    return ChatSession.objects.create(session_key=request.session.session_key)


def _sse(event, data):
    return f'event: {event}\ndata: {json.dumps(data)}\n\n'


@require_POST
def chat(request):
    """POST /basil/chat/ -> SSE stream (MASTER_SPEC §10.3)."""
    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'Malformed request body.'}, status=400)

    message = (payload.get('message') or '').strip()
    image_id = payload.get('image_id')
    if not message and not image_id:
        return JsonResponse({'error': 'Say something first.'}, status=400)

    session_id = payload.get('session_id')
    if session_id:
        # for_request is the tenancy boundary: an id alone is not access.
        try:
            session = ChatSession.objects.for_request(request).filter(
                pk=session_id).first()
        except (ValidationError, ValueError):
            session = None
        if session is None:
            return JsonResponse({'error': 'Unknown chat session.'}, status=404)
    else:
        session = get_or_create_session(request)

    if image_id:
        # The id is resolved against the caller's own sessions, so it is the
        # server that names the image Basil may look at, not the message text.
        try:
            image = UploadedImage.objects.filter(
                session__in=ChatSession.objects.for_request(request),
                pk=image_id,
            ).first()
        except (ValidationError, ValueError):
            image = None
        if image is None:
            return JsonResponse({'error': 'Unknown image.'}, status=404)

        if image.session_id != session.id:
            # Same visitor, older session. vision_identify is session-scoped.
            image.session = session
            image.save(update_fields=['session'])

        marker = IMAGE_MARKER.format(image_id=image.id)
        message = f'{marker}\n{message}'.strip()

    user = request.user if request.user.is_authenticated else None

    def events():
        yield _sse('session', {'session_id': str(session.id)})
        for event, data in run_turn(session, message, user=user):
            yield _sse(event, data)

    response = StreamingHttpResponse(
        events(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    # Stops nginx buffering the stream into one lump.
    response['X-Accel-Buffering'] = 'no'
    return response


def _replay(message):
    """One stored row as the rail should draw it, or None to skip it.

    tool_use and tool_result rows are the model's working, not conversation.
    """
    if message.role == ChatMessage.Role.USER:
        text = message.content if isinstance(message.content, str) else ''
        image_url = ''

        match = IMAGE_MARKER_RE.match(text)
        if match:
            # The marker is addressed to the model. Show the photo instead.
            text = IMAGE_MARKER_RE.sub('', text).strip()
            image = UploadedImage.objects.filter(pk=match.group(1)).first()
            if image:
                image_url = image.image.url

        if not text and not image_url:
            return None
        return {'role': 'user', 'text': text, 'image_url': image_url}

    if message.role == ChatMessage.Role.ASSISTANT:
        blocks = message.content if isinstance(message.content, list) else []
        text = ''.join(b.get('text', '') for b in blocks
                       if isinstance(b, dict) and b.get('type') == 'text')
        return {'role': 'assistant', 'text': text} if text.strip() else None

    return None


@require_GET
def history(request):
    """GET /basil/history/ -> the caller's conversation, so it survives a page
    change. The messages live in the DB; the rail only redraws them."""
    session = ChatSession.objects.for_request(request).first()
    if session is None:
        return JsonResponse({'session_id': '', 'messages': []})

    # The most recent HISTORY_LIMIT, back in reading order. A plain [:limit]
    # on the ascending default would return the oldest instead.
    rows = reversed(session.messages.order_by('-created_at', '-id')[:HISTORY_LIMIT])
    messages = [drawn for drawn in (_replay(row) for row in rows) if drawn]

    return JsonResponse({'session_id': str(session.id), 'messages': messages})


@require_POST
def upload_image(request):
    """POST /basil/upload-image/ -> {image_id} (MASTER_SPEC §8.2)."""
    upload = request.FILES.get('image')
    if upload is None:
        return JsonResponse({'error': 'No image supplied.'}, status=400)

    if upload.size > settings.BASIL_MAX_UPLOAD_BYTES:
        limit_mb = settings.BASIL_MAX_UPLOAD_BYTES // (1024 * 1024)
        return JsonResponse(
            {'error': f'Image must be smaller than {limit_mb} MB.'}, status=400)

    if upload.content_type not in ALLOWED_TYPES:
        return JsonResponse({'error': 'Only JPEG or PNG images.'}, status=400)

    # content_type is client-supplied, so check the bytes too. imghdr was
    # removed in Python 3.13; Pillow is stricter anyway.
    try:
        with Image.open(upload) as probe:
            image_format = probe.format
    except (UnidentifiedImageError, OSError):
        image_format = None
    finally:
        upload.seek(0)

    if image_format not in ALLOWED_FORMATS:
        return JsonResponse({'error': 'That file is not a JPEG or PNG.'}, status=400)

    image = UploadedImage.objects.create(
        session=get_or_create_session(request), image=upload)
    return JsonResponse({'image_id': str(image.id)})
