
import io
import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from products.models import Product
from products.test_utils import make_product

from . import agent
from .models import ChatMessage, ChatSession, UploadedImage
from users.test_utils import ADULT_DOB

User = get_user_model()


def _png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), 'brown').save(buffer, format='PNG')
    return buffer.getvalue()


class FakeBlock:
    """Stands in for an SDK content block, which the agent model_dumps."""

    def __init__(self, **data):
        self._data = data
        self.type = data['type']

    def model_dump(self, exclude_none=False):
        return dict(self._data)


# Agent loop and SSE tests

def text_block(text):
    return FakeBlock(type='text', text=text)


def tool_block(name, tool_input, block_id='tu_1'):
    return FakeBlock(type='tool_use', id=block_id, name=name, input=tool_input)


class FakeMessage:
    def __init__(self, blocks):
        self.content = blocks


class FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        for block in self._message.content:
            if block.type == 'text':
                yield block._data['text']

    def get_final_message(self):
        return self._message


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def stream(self, **kwargs):
        # Snapshot: the agent keeps mutating the same messages list.
        self.calls.append({**kwargs, 'messages': list(kwargs['messages'])})
        blocks = self.replies.pop(0) if self.replies else [text_block('...')]
        return FakeStream(FakeMessage(blocks))


class FakeClient:
    def __init__(self, replies):
        self.messages = FakeMessages(replies)


def fake_client(*replies):
    """Patch get_client to return a client scripted with these replies."""
    client = FakeClient(replies)
    return patch.object(agent, 'get_client', lambda: client), client


class RunTurnTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='ana', password='pw', email='ana@example.com')
        self.session = ChatSession.objects.create(user=self.user)
        make_product('Dessert', name='Tiramisu', description='d', price=5.50,
                     stock=4)

    def test_plain_reply_streams_tokens_and_persists(self):
        patcher, client = fake_client([text_block('Hey '), text_block('there')])
        with patcher:
            events = list(agent.run_turn(self.session, 'hi', user=self.user))

        tokens = [d['text'] for name, d in events if name == 'token']
        self.assertEqual(tokens, ['Hey ', 'there'])
        self.assertEqual(events[-1][0], 'done')

        rows = list(self.session.messages.all())
        self.assertEqual([r.role for r in rows], ['user', 'assistant'])
        self.assertEqual(rows[0].content, 'hi')
        self.assertEqual(len(client.messages.calls), 1)

    def test_tool_use_pauses_runs_the_tool_and_resumes(self):
        patcher, client = fake_client(
            [tool_block('search_menu', {'query': 'tiramisu'})],
            [text_block('We have Tiramisu.')],
        )
        with patcher:
            events = list(agent.run_turn(self.session, 'tiramisu?',
                                         user=self.user))

        names = [name for name, _ in events]
        self.assertIn('tool_start', names)
        self.assertIn('tool_end', names)
        self.assertEqual(len(client.messages.calls), 2)

        roles = [r.role for r in self.session.messages.all()]
        self.assertEqual(roles, ['user', 'tool_use', 'tool_result', 'assistant'])

        # The tool actually ran against the catalog, not against the model.
        result = self.session.messages.get(role='tool_result').content[0]
        self.assertFalse(result['is_error'])
        self.assertIn('Tiramisu', result['content'])

        # The resumed request carries the tool_result back.
        second = client.messages.calls[1]['messages']
        self.assertEqual(second[-1]['role'], 'user')
        self.assertEqual(second[-1]['content'][0]['type'], 'tool_result')

    def test_tools_are_dispatched_with_the_real_caller(self):
        """A forged user in tool input must not choose whose orders are read."""
        patcher, client = fake_client(
            [tool_block('read_orders', {'user': 'someone_else'})],
            [text_block('Nothing yet.')],
        )
        with patcher:
            list(agent.run_turn(self.session, 'my orders?', user=self.user))

        result = self.session.messages.get(role='tool_result').content[0]
        self.assertNotIn('Please sign in', result['content'])

    def test_a_failing_tool_does_not_kill_the_turn(self):
        patcher, _ = fake_client(
            [tool_block('no_such_tool', {})],
            [text_block('Sorry about that.')],
        )
        with patcher:
            events = list(agent.run_turn(self.session, 'x', user=self.user))

        result = self.session.messages.get(role='tool_result').content[0]
        self.assertTrue(result['is_error'])
        self.assertEqual(events[-1][0], 'done')

    def test_iteration_cap_stops_the_loop(self):
        """The cap is enforced in code -- the model is not trusted to count."""
        forever = [[tool_block('search_menu', {'query': 'x'})] for _ in range(20)]
        patcher, client = fake_client(*forever)
        with patcher:
            events = list(agent.run_turn(self.session, 'loop', user=self.user))

        cap = 8
        # cap tool-calling requests, then one final request with tools barred.
        self.assertEqual(len(client.messages.calls), cap + 1)
        self.assertEqual(
            client.messages.calls[-1]['tool_choice'], {'type': 'none'})
        self.assertNotIn('tool_choice', client.messages.calls[0])
        self.assertEqual(events[-1][0], 'done')

    def test_api_failure_becomes_an_error_event(self):
        def boom():
            raise RuntimeError('no key')

        with patch.object(agent, 'get_client', boom):
            events = list(agent.run_turn(self.session, 'hi', user=self.user))

        self.assertEqual(events[0][0], 'error')
        self.assertEqual(events[-1][0], 'done')

    def test_history_is_replayed_in_api_shape(self):
        ChatMessage.objects.create(
            session=self.session, role='user', content='hi')
        ChatMessage.objects.create(
            session=self.session, role='tool_use',
            content=[{'type': 'tool_use', 'id': 't', 'name': 'search_menu',
                      'input': {}}])
        ChatMessage.objects.create(
            session=self.session, role='tool_result',
            content=[{'type': 'tool_result', 'tool_use_id': 't',
                      'content': '{}'}])

        history = agent.load_history(self.session)
        self.assertEqual([m['role'] for m in history],
                         ['user', 'assistant', 'user'])


class ClientHeaderTestCase(TestCase):
    """An identity-linked key is rejected with a 400 unless the request names
    its workspace."""

    def setUp(self):
        agent._client = None

    def tearDown(self):
        agent._client = None

    @override_settings(BASIL_API_KEY='sk-test', BASIL_WORKSPACE_ID='wrk_123')
    def test_workspace_id_is_sent_when_configured(self):
        client = agent.get_client()
        self.assertEqual(
            client.default_headers.get('anthropic-workspace-id'), 'wrk_123')

    @override_settings(BASIL_API_KEY='sk-test', BASIL_WORKSPACE_ID='')
    def test_no_header_without_a_workspace(self):
        client = agent.get_client()
        self.assertNotIn('anthropic-workspace-id', client.default_headers)

    @override_settings(BASIL_API_KEY='')
    def test_a_missing_key_is_a_clear_error(self):
        with self.assertRaises(RuntimeError):
            agent.get_client()


class RailMarkupTestCase(TestCase):
    """The composer was deliberately disabled until the agent was live."""

    def test_the_composer_is_enabled_and_wired(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('id="basil-form"', html)
        self.assertIn('id="basil-drop"', html)
        self.assertNotIn('Basil is not connected yet', html)
        # chat.js posts JSON, so the token has to come from the page.
        self.assertIn('csrfmiddlewaretoken', html)

    def test_the_drop_overlay_starts_hidden(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('<div id="basil-drop" hidden', html)

    def test_hidden_beats_display_utilities(self):
        """The overlay carries both `hidden` and `flex`, and a display utility
        outranks the browser's [hidden] rule -- it covered the whole chat until
        this rule was added. input.css is source, not a build artifact."""
        css = (settings.BASE_DIR / 'static' / 'src' / 'input.css').read_text()
        self.assertIn('display: none !important', css)


class ChatEndpointTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='ana', password='pw', email='ana@example.com')
        self.url = reverse('basil_chat')

    def _events(self, response):
        body = b''.join(response.streaming_content).decode()
        return [line[len('event: '):] for line in body.splitlines()
                if line.startswith('event: ')]

    def test_streams_sse(self):
        patcher, _ = fake_client([text_block('Hello')])
        self.client.force_login(self.user)
        with patcher:
            response = self.client.post(
                self.url, json.dumps({'message': 'hi'}),
                content_type='application/json')
            events = self._events(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
        self.assertEqual(response['X-Accel-Buffering'], 'no')
        self.assertEqual(events, ['session', 'token', 'done'])

    def test_anonymous_can_chat(self):
        patcher, _ = fake_client([text_block('Hello')])
        with patcher:
            response = self.client.post(
                self.url, json.dumps({'message': 'hi'}),
                content_type='application/json')
            self.assertIn('token', self._events(response))

        self.assertEqual(response.status_code, 200)

    def test_empty_message_is_rejected(self):
        response = self.client.post(self.url, json.dumps({'message': '  '}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_cannot_post_into_another_visitors_session(self):
        bob = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='bob', password='pw', email='bob@example.com')
        theirs = ChatSession.objects.create(user=bob)

        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            json.dumps({'message': 'hi', 'session_id': str(theirs.id)}),
            content_type='application/json')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(theirs.messages.count(), 0)

    def _upload(self):
        image = SimpleUploadedFile('cake.png', _png_bytes(), 'image/png')
        response = self.client.post(reverse('basil_upload_image'),
                                    {'image': image})
        return response.json()['image_id']

    def test_an_uploaded_image_reaches_the_model_as_an_id(self):
        self.client.force_login(self.user)
        image_id = self._upload()

        patcher, client = fake_client([text_block('Nice cake.')])
        with patcher:
            response = self.client.post(
                self.url,
                json.dumps({'message': 'what is this?', 'image_id': image_id}),
                content_type='application/json')
            self._events(response)

        # The server writes the id into the turn; the browser never has to.
        sent = client.messages.calls[0]['messages'][0]['content']
        self.assertIn(image_id, sent)
        self.assertIn('what is this?', sent)

    def test_a_photo_alone_is_enough(self):
        self.client.force_login(self.user)
        image_id = self._upload()

        patcher, _ = fake_client([text_block('Looks like cake.')])
        with patcher:
            response = self.client.post(
                self.url, json.dumps({'image_id': image_id}),
                content_type='application/json')
            self.assertIn('token', self._events(response))

    def test_cannot_attach_another_visitors_image(self):
        bob = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='bob', password='pw', email='bob@example.com')
        theirs = UploadedImage.objects.create(
            session=ChatSession.objects.create(user=bob),
            image=SimpleUploadedFile('x.png', _png_bytes(), 'image/png'))

        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            json.dumps({'message': 'hi', 'image_id': str(theirs.id)}),
            content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_unknown_image_id_is_a_404_not_a_500(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, json.dumps({'message': 'hi', 'image_id': 'nope'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_unparseable_session_id_is_a_404_not_a_500(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, json.dumps({'message': 'hi', 'session_id': 'nope'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 404)


class HistoryEndpointTestCase(TestCase):
    """The conversation lives in the DB, so it survives a page change."""

    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='ana', password='pw', email='ana@example.com')
        self.url = reverse('basil_history')

    def _talk(self, message='hi', reply='hello there'):
        patcher, _ = fake_client([text_block(reply)])
        with patcher:
            response = self.client.post(
                reverse('basil_chat'), json.dumps({'message': message}),
                content_type='application/json')
            b''.join(response.streaming_content)

    def test_a_conversation_comes_back_after_a_page_change(self):
        self.client.force_login(self.user)
        self._talk('do you have cake?', 'we do')

        data = self.client.get(self.url).json()

        self.assertEqual([m['role'] for m in data['messages']],
                         ['user', 'assistant'])
        self.assertEqual(data['messages'][0]['text'], 'do you have cake?')
        self.assertEqual(data['messages'][1]['text'], 'we do')
        self.assertTrue(data['session_id'])

    def test_an_anonymous_visitor_keeps_their_own_thread(self):
        self._talk('anything vegan?', 'let me look')
        data = self.client.get(self.url).json()
        self.assertEqual(len(data['messages']), 2)

    def test_a_fresh_visitor_gets_an_empty_thread(self):
        data = self.client.get(self.url).json()
        self.assertEqual(data['messages'], [])
        self.assertEqual(data['session_id'], '')

    def test_one_visitor_cannot_read_another(self):
        self.client.force_login(self.user)
        self._talk('my private question', 'sure')

        bob = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='bob', password='pw', email='bob@example.com')
        self.client.force_login(bob)
        data = self.client.get(self.url).json()

        self.assertEqual(data['messages'], [])

    def test_tool_rows_are_not_conversation(self):
        """tool_use and tool_result are the model's working, not messages."""
        session = ChatSession.objects.create(user=self.user)
        ChatMessage.objects.create(session=session, role='user', content='hi')
        ChatMessage.objects.create(
            session=session, role='tool_use',
            content=[{'type': 'tool_use', 'id': 't', 'name': 'search_menu',
                      'input': {}}])
        ChatMessage.objects.create(
            session=session, role='tool_result',
            content=[{'type': 'tool_result', 'tool_use_id': 't', 'content': '{}'}])
        ChatMessage.objects.create(
            session=session, role='assistant',
            content=[{'type': 'text', 'text': 'we have cake'}])

        self.client.force_login(self.user)
        data = self.client.get(self.url).json()

        self.assertEqual([m['role'] for m in data['messages']],
                         ['user', 'assistant'])

    def test_an_assistant_turn_of_pure_tool_use_is_skipped(self):
        session = ChatSession.objects.create(user=self.user)
        ChatMessage.objects.create(
            session=session, role='assistant',
            content=[{'type': 'tool_use', 'id': 't', 'name': 'x', 'input': {}}])

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).json()['messages'], [])

    def test_a_photo_turn_shows_the_photo_not_the_marker(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile('cake.png', _png_bytes(), 'image/png')
        image_id = self.client.post(reverse('basil_upload_image'),
                                    {'image': upload}).json()['image_id']

        patcher, _ = fake_client([text_block('nice')])
        with patcher:
            response = self.client.post(
                reverse('basil_chat'),
                json.dumps({'message': 'what is this?', 'image_id': image_id}),
                content_type='application/json')
            b''.join(response.streaming_content)

        first = self.client.get(self.url).json()['messages'][0]

        self.assertEqual(first['text'], 'what is this?')
        self.assertNotIn('image_id', first['text'])
        self.assertTrue(first['image_url'])

    def test_only_the_most_recent_messages_are_returned(self):
        session = ChatSession.objects.create(user=self.user)
        for i in range(70):
            ChatMessage.objects.create(
                session=session, role='user', content=f'message {i}')

        self.client.force_login(self.user)
        messages = self.client.get(self.url).json()['messages']

        self.assertEqual(len(messages), 60)
        # The newest, in reading order -- not the oldest.
        self.assertEqual(messages[0]['text'], 'message 10')
        self.assertEqual(messages[-1]['text'], 'message 69')

    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
