
import json
import logging

import anthropic
from django.conf import settings

from .models import ChatMessage
from .tools import TOOL_SCHEMAS, dispatch

logger = logging.getLogger(__name__)

MAX_TOKENS = 2048
SYSTEM_PROMPT_PATH = settings.BASE_DIR / 'basil' / 'prompts' / 'system_prompt.md'

_client = None
_system_prompt = None

# The agent loop  

def get_client():
    """One shared client. The key never leaves the server."""
    global _client
    
    if _client is None:
        
        if not settings.BASIL_API_KEY:
            raise RuntimeError('BASIL_API_KEY is not set.')
        
        headers = {}
        
        if settings.BASIL_WORKSPACE_ID:
            headers['anthropic-workspace-id'] = settings.BASIL_WORKSPACE_ID
            
        _client = anthropic.Anthropic(
            api_key=settings.BASIL_API_KEY, default_headers=headers)
    return _client


def get_system_prompt():
    
    global _system_prompt
    
    if _system_prompt is None:
        _system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding='utf-8')

    # The model cannot guess our category names, and a guess like "drinks"
    # matches nothing and reads to the customer as "we sell none of that".
    # Appended live so a category added in the admin is usable immediately.
    from .tools.menu import list_category_names
    names = list_category_names()
    
    if not names:
        
        return _system_prompt

    # let us Basil know what categories are available
    return (f'{_system_prompt}\n\n## Menu categories\n\n'
            f'The only valid values for search_menu category are: '
            f'{", ".join(names)}. A product belongs to several at once — an '
            f'iced latte is Coffee, Iced, Espresso and Milky. Never pass a '
            f'category name that is not on this list.')


# ChatMessage.role -> the role the API expects. tool_use is an assistant turn
# and tool_result a user turn; the extra roles exist so the transcript is
# readable, not because the API knows them.
_API_ROLE = {
    ChatMessage.Role.USER: 'user',
    ChatMessage.Role.ASSISTANT: 'assistant',
    ChatMessage.Role.TOOL_USE: 'assistant',
    ChatMessage.Role.TOOL_RESULT: 'user',
}


def _sort_json_keys(content):
    """Sorted-key JSON. jsonb reorders keys on save, so the live loop and a
    replay from the DB must agree byte for byte or the cached prefix misses."""
    return json.loads(json.dumps(content, sort_keys=True))


def load_history(session):
    """Replay a session as Anthropic message params."""
    return [
        {'role': _API_ROLE[row.role], 'content': _sort_json_keys(row.content)}
        for row in session.messages.all()
        if row.role in _API_ROLE
    ]


def _blocks(message):
    """SDK content blocks as plain JSON, safe to store and to resend."""
    return _sort_json_keys(
        [block.model_dump(exclude_none=True) for block in message.content])


def _cached_system():
    """System prompt as one cached block, so tools + system are shared across
    every session. Below the model's minimum prefix it silently does not cache."""
    return [{'type': 'text', 'text': get_system_prompt(),
             'cache_control': {'type': 'ephemeral'}}]


def _log_usage(reply):
    usage = getattr(reply, 'usage', None)
    if usage is None:
        return
    logger.info('basil usage: input=%s cache_read=%s cache_write=%s output=%s',
                usage.input_tokens,
                getattr(usage, 'cache_read_input_tokens', 0),
                getattr(usage, 'cache_creation_input_tokens', 0),
                usage.output_tokens)


def run_turn(session, user_text, user=None):
    """Yield (event, data) for one user turn. Never raises to the caller."""
    try:
        yield from _run_turn(session, user_text, user)
        
    except anthropic.APIStatusError as exc:
        logger.exception('Basil API error')
        yield 'error', {'message': f'Basil could not reply ({exc.status_code}).'}
        
    except Exception as exc:
        logger.exception('Basil turn failed')
        yield 'error', {'message': f'Basil could not reply: {exc}, Please Try later.'}
        
    yield 'done', {}


# Event SSE stream
def _run_turn(session, user_text, user):
    
    messages = load_history(session)
    messages.append({'role': 'user', 'content': user_text})
    
    ChatMessage.objects.create(
        session=session, 
        role=ChatMessage.Role.USER, 
        content=user_text)

    client = get_client()
    cap = settings.BASIL_MAX_TOOL_ITERATIONS
    tool_calls = 0

    while True:
        # At the cap the model keeps its tools declared but may not call them,
        # so it has to answer with what it already has (§5.3).
        capped = tool_calls >= cap
        kwargs = {'tool_choice': {'type': 'none'}} if capped else {}

        # Top-level cache_control puts the second breakpoint on the last
        # message, so each tool round and each new turn reads the conversation
        # so far from cache instead of paying for it again.
        with client.messages.stream(
            model=settings.BASIL_LLM_MODEL,
            max_tokens=MAX_TOKENS,
            system=_cached_system(),
            tools=TOOL_SCHEMAS,
            messages=messages,
            cache_control={'type': 'ephemeral'},
            **kwargs,
        ) as stream:
            for text in stream.text_stream:

                yield 'token', {'text': text}

            reply = stream.get_final_message()

        _log_usage(reply)

        blocks = _blocks(reply)
        uses = [b for b in blocks if b.get('type') == 'tool_use']
        role = ChatMessage.Role.TOOL_USE if uses else ChatMessage.Role.ASSISTANT
        ChatMessage.objects.create(session=session, role=role, content=blocks)
        messages.append({'role': 'assistant', 'content': blocks})

        # At the cap the turn ends here whatever came back. tool_choice none
        # should have prevented a tool_use block; the loop does not depend on
        # the model having honoured it.
        if not uses or capped:
            return

        # Every tool_use needs a tool_result in one user message, or the next
        # request is rejected.
        results = []
        
        for use in uses:
            
            yield 'tool_start', {'name': use['name']}
            output = dispatch(use['name'], 
                              use.get('input'), 
                              user=user,
                              session=session)
            
            results.append({
                'type': 'tool_result',
                'tool_use_id': use['id'],
                'content': json.dumps(output, 
                                      default=str
                                      ),
                'is_error': 'error' in output,
            })
            yield 'tool_end', {'name': use['name']}

        tool_calls += len(uses)
        
        ChatMessage.objects.create(
            session=session, 
            role=ChatMessage.Role.TOOL_RESULT, 
            content=results
            )
        
        messages.append({'role': 'user', 'content': _sort_json_keys(results)})


 