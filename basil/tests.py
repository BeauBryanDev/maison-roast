"""Basil tests. No test may call the Anthropic or Voyage APIs (MASTER_SPEC §5.3)."""

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from .models import ChatMessage, ChatSession, UploadedImage
from users.test_utils import ADULT_DOB

User = get_user_model()


class _Anon:
    is_authenticated = False


def _request(user=None, session_key=None):
    request = RequestFactory().get('/')
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    if session_key:
        request.session._session_key = session_key
    request.user = user if user is not None else _Anon()
    return request


class ChatSessionTenancyTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='alice', password='pw', email='alice@example.com')
        self.bob = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='bob', password='pw', email='bob@example.com')
        self.alice_session = ChatSession.objects.create(user=self.alice)
        self.bob_session = ChatSession.objects.create(user=self.bob)

    def test_user_sees_only_their_own_sessions(self):
        visible = ChatSession.objects.for_request(_request(user=self.alice))
        self.assertIn(self.alice_session, visible)
        self.assertNotIn(self.bob_session, visible)

    def test_anonymous_sees_no_user_owned_sessions(self):
        visible = ChatSession.objects.for_request(_request())
        self.assertNotIn(self.alice_session, visible)
        self.assertNotIn(self.bob_session, visible)

    def test_anonymous_sees_only_their_own_session_key(self):
        mine = ChatSession.objects.create(session_key='key-mine')
        theirs = ChatSession.objects.create(session_key='key-theirs')

        visible = ChatSession.objects.for_request(_request(session_key='key-mine'))

        self.assertIn(mine, visible)
        self.assertNotIn(theirs, visible)

    def test_anonymous_without_a_session_key_sees_nothing(self):
        request = _request()
        request.session._session_key = None

        self.assertEqual(ChatSession.objects.for_request(request).count(), 0)

    def test_signing_in_does_not_expose_anonymous_sessions(self):
        anon_session = ChatSession.objects.create(session_key='key-mine')

        visible = ChatSession.objects.for_request(
            _request(user=self.alice, session_key='key-mine'))

        self.assertNotIn(anon_session, visible)


class ChatMessageTestCase(TestCase):
    def setUp(self):
        self.session = ChatSession.objects.create(session_key='k')

    def test_history_replays_in_order(self):
        for i in range(5):
            ChatMessage.objects.create(
                session=self.session, role=ChatMessage.Role.USER,
                content={'text': f'turn {i}'})

        texts = [m.content['text'] for m in self.session.messages.all()]
        self.assertEqual(texts, [f'turn {i}' for i in range(5)])

    def test_content_round_trips_a_tool_use_block(self):
        payload = {
            'type': 'tool_use',
            'name': 'search_menu',
            'input': {'query': 'tiramisu', 'limit': 10},
        }
        message = ChatMessage.objects.create(
            session=self.session, role=ChatMessage.Role.TOOL_USE, content=payload)
        message.refresh_from_db()

        self.assertEqual(message.content, payload)
        self.assertEqual(message.content['input']['limit'], 10)

    def test_deleting_a_session_removes_its_messages(self):
        ChatMessage.objects.create(
            session=self.session, role=ChatMessage.Role.USER, content={'text': 'hi'})
        self.session.delete()

        self.assertEqual(ChatMessage.objects.count(), 0)


class UploadedImageTestCase(TestCase):
    def test_image_belongs_to_its_session_and_cascades(self):
        session = ChatSession.objects.create(session_key='k')
        UploadedImage.objects.create(session=session, image='basil_uploads/x.jpg')

        self.assertEqual(session.images.count(), 1)
        session.delete()
        self.assertEqual(UploadedImage.objects.count(), 0)
