
import io

import numpy as np
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import ChatSession, UploadedImage
from .vision.infer import IMG_SIZE, preprocess
from .vision.labels import UNKNOWN_LABEL, index_to_label


def make_image(size=(800, 600), colour=(200, 120, 60), fmt='JPEG'):
    buffer = io.BytesIO()
    Image.new('RGB', size, colour).save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


def upload_file(name='food.jpg', content_type='image/jpeg', fmt='JPEG', size=(64, 64)):
    return SimpleUploadedFile(name, make_image(size, fmt=fmt).read(), content_type)


# VISION — ONNX inference tests

class PreprocessTestCase(TestCase):
    def test_shape_is_nhwc_batch_of_one(self):
        # The graph came from TensorFlow, so it is NHWC. NCHW would be silently wrong.
        batch = preprocess(make_image())
        self.assertEqual(batch.shape, (1, IMG_SIZE, IMG_SIZE, 3))

    def test_dtype_is_float32(self):
        self.assertEqual(preprocess(make_image()).dtype, np.float32)

    def test_values_stay_in_0_255(self):
        # EfficientNetV2 normalizes internally; dividing by 255 here would halve
        # every activation and quietly wreck the predictions.
        batch = preprocess(make_image(colour=(255, 255, 255)))
        self.assertGreater(batch.max(), 1.0)
        self.assertLessEqual(batch.max(), 255.0)

    def test_grayscale_input_becomes_three_channels(self):
        buffer = io.BytesIO()
        Image.new('L', (100, 100), 128).save(buffer, format='JPEG')
        buffer.seek(0)
        self.assertEqual(preprocess(buffer).shape[-1], 3)

    def test_non_square_input_is_resized_not_cropped(self):
        self.assertEqual(preprocess(make_image((1200, 300))).shape[1:3],
                         (IMG_SIZE, IMG_SIZE))


class LabelMapTestCase(TestCase):
    def test_labels_align_with_model_output_width(self):
        self.assertEqual(len(index_to_label()), 41)

    def test_unknown_is_the_last_class(self):
        self.assertEqual(index_to_label()[40], UNKNOWN_LABEL)


class ModelContractTestCase(TestCase):
    """Guards facts about the exported graph that the tool code relies on."""

    def setUp(self):
        if not settings.BASIL_MODEL_PATH.exists():
            self.skipTest('ONNX model not present')
        from .vision.infer import get_session
        self.session = get_session()

    def test_input_signature_is_384_nhwc(self):
        spec = self.session.get_inputs()[0]
        self.assertEqual(list(spec.shape[1:]), [IMG_SIZE, IMG_SIZE, 3])
        self.assertEqual(spec.type, 'tensor(float)')

    def test_output_is_already_softmaxed(self):
        # The last Keras layer was Dense(activation="softmax"). Applying softmax
        # again would push every top-1 below the 0.60 threshold, so every photo
        # would come back is_unknown with no error anywhere.
        name = self.session.get_inputs()[0].name
        probe = np.random.uniform(0, 255, (1, IMG_SIZE, IMG_SIZE, 3)).astype(np.float32)
        out = self.session.run(None, {name: probe})[0]

        self.assertEqual(out.shape, (1, 41))
        self.assertAlmostEqual(float(out.sum()), 1.0, places=4)


@override_settings(MEDIA_ROOT='/tmp/basil_test_media')
class AlternativesFilterTestCase(TestCase):
    """MASTER_SPEC §4.6: unknown must never be offered to the agent as an
    alternative. Exercises the real filtering by faking the session output."""

    def _predict_with(self, probabilities):
        from .vision import infer

        class FakeSession:
            def get_inputs(self):
                return [type('S', (), {'name': 'input'})()]

            def run(self, _outputs, _feed):
                return [np.asarray([probabilities], dtype=np.float32)]

        original = infer._session
        infer._session = FakeSession()
        try:
            return infer.predict(make_image())
        finally:
            infer._session = original

    def test_unknown_is_dropped_from_alternatives(self):
        probabilities = np.full(41, 0.001, dtype=np.float32)
        probabilities[38] = 0.70   # tiramisu wins
        probabilities[40] = 0.25   # unknown would otherwise be second

        label, confidence, alternatives = self._predict_with(probabilities)

        self.assertEqual(label, 'tiramisu')
        self.assertNotIn(UNKNOWN_LABEL, [a['label'] for a in alternatives])

    def test_unknown_winning_is_still_reported_as_the_prediction(self):
        # Dropped from alternatives, not from the prediction itself -- the tool
        # needs it to set is_unknown.
        probabilities = np.full(41, 0.001, dtype=np.float32)
        probabilities[40] = 0.90

        label, confidence, alternatives = self._predict_with(probabilities)

        self.assertEqual(label, UNKNOWN_LABEL)
        self.assertNotIn(UNKNOWN_LABEL, [a['label'] for a in alternatives])


class VisionToolTestCase(TestCase):
    def setUp(self):
        self.session = ChatSession.objects.create(session_key='k')

    def _image(self, session=None):
        """An UploadedImage whose file really exists on disk."""
        return UploadedImage.objects.create(
            session=session or self.session, image=upload_file())

    def test_missing_image_is_an_error_not_an_exception(self):
        from .tools.vision import vision_identify
        result = vision_identify('00000000-0000-0000-0000-000000000000')
        self.assertIn('error', result)

    def test_image_from_another_session_is_not_readable(self):
        from .tools.vision import vision_identify
        other = ChatSession.objects.create(session_key='other')
        image = self._image(session=other)

        result = vision_identify(str(image.id), session=self.session)

        self.assertIn('error', result)

    def test_unknown_label_forces_is_unknown(self):
        from .tools import vision as vision_tool
        image = self._image()

        def fake_predict(handle, top_k=3):
            return UNKNOWN_LABEL, 0.99, []

        original = vision_tool.predict
        vision_tool.predict = fake_predict
        try:
            with self.settings(BASIL_UNKNOWN_THRESHOLD=0.60):
                result = vision_tool.vision_identify(str(image.id))
        finally:
            vision_tool.predict = original

        # High confidence, but the class itself is unknown.
        self.assertTrue(result['is_unknown'])

    def test_low_confidence_forces_is_unknown(self):
        from .tools import vision as vision_tool
        image = self._image()

        def fake_predict(handle, top_k=3):
            return 'tiramisu', 0.42, [{'label': 'cannoli', 'confidence': 0.2}]

        original = vision_tool.predict
        vision_tool.predict = fake_predict
        try:
            result = vision_tool.vision_identify(str(image.id))
        finally:
            vision_tool.predict = original

        self.assertTrue(result['is_unknown'])
        self.assertEqual(result['prediction']['label'], 'tiramisu')


@override_settings(MEDIA_ROOT='/tmp/basil_test_media')
class UploadEndpointTestCase(TestCase):
    def setUp(self):
        self.url = reverse('basil_upload_image')

    def test_jpeg_upload_returns_an_image_id(self):
        response = self.client.post(self.url, {'image': upload_file()})
        self.assertEqual(response.status_code, 200)
        self.assertIn('image_id', response.json())
        self.assertEqual(UploadedImage.objects.count(), 1)

    def test_anonymous_upload_is_allowed(self):
        # Anonymous visitors are first-class (MASTER_SPEC §2.6).
        response = self.client.post(self.url, {'image': upload_file()})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(UploadedImage.objects.get().session.user)

    def test_missing_file_is_rejected(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)

    def test_wrong_content_type_is_rejected(self):
        bad = SimpleUploadedFile('note.txt', b'not an image', 'text/plain')
        self.assertEqual(self.client.post(self.url, {'image': bad}).status_code, 400)
        self.assertEqual(UploadedImage.objects.count(), 0)

    def test_lying_content_type_is_rejected(self):
        # content_type is client-supplied, so the bytes are checked too.
        liar = SimpleUploadedFile('evil.jpg', b'MZ\x00 not an image', 'image/jpeg')
        self.assertEqual(self.client.post(self.url, {'image': liar}).status_code, 400)
        self.assertEqual(UploadedImage.objects.count(), 0)

    def test_oversize_upload_is_rejected(self):
        with self.settings(BASIL_MAX_UPLOAD_BYTES=100):
            response = self.client.post(self.url, {'image': upload_file()})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(UploadedImage.objects.count(), 0)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
