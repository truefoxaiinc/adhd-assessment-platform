import asyncio
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from channels.testing import WebsocketCommunicator
from django.conf import settings


if not settings.configured:
    settings.configure(
        SECRET_KEY="test-secret-key",
        CHANNEL_LAYERS={
            "default": {
                "BACKEND": "channels.layers.InMemoryChannelLayer",
            },
        },
    )

face_analysis_service = types.ModuleType("apps.websocket.services.face_analysis_service")
face_analysis_service.analyze_face_attention = lambda face_analysis_data: {}
sys.modules["apps.websocket.services.face_analysis_service"] = face_analysis_service

from apps.websocket.consumers import FaceDetectionConsumer


VALID_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
SAFE_ERROR_RESPONSE = {
    "type": "error",
    "error_code": "FACE_VALIDATION_FAILED",
    "message": "Unable to process frame safely",
}
FRAME_TOO_LARGE_RESPONSE = {
    "type": "error",
    "error_code": "FRAME_TOO_LARGE",
    "message": "Frame is too large",
}
FRAME_SKIPPED_RESULT = {
    "frame_sampled": False,
    "message": "Frame skipped",
}


class FakeDecodedFrame:
    def __init__(self, width, height):
        self.shape = (height, width, 3)


@pytest.fixture
def user():
    return SimpleNamespace(id=1, is_authenticated=True)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def disable_score_persistence(monkeypatch):
    async def noop_save_assessment_score(self):
        self.assessment_score_saved = True

    monkeypatch.setattr(
        FaceDetectionConsumer,
        "_save_assessment_score",
        noop_save_assessment_score,
    )


def communicator_for_user(user=None):
    communicator = WebsocketCommunicator(FaceDetectionConsumer.as_asgi(), "/ws/face-detection/")
    if user is not None:
        communicator.scope["user"] = user
    return communicator


async def connect_authenticated(user):
    communicator = communicator_for_user(user)
    connected, _ = await communicator.connect()
    assert connected is True
    welcome = await communicator.receive_json_from(timeout=1)
    assert welcome["type"] == "connection_established"
    return communicator


def assert_safe_error_response(response):
    assert response == SAFE_ERROR_RESPONSE


def assert_frame_too_large_response(response):
    assert response == FRAME_TOO_LARGE_RESPONSE


def validate_face_payload():
    return {
        "type": "validate_face",
        "face": {"x": 0, "y": 0, "width": 1, "height": 1},
        "frame": {"width": 1, "height": 1},
        "frame_base64": VALID_PNG_BASE64,
    }


async def send_validate_face(communicator):
    await communicator.send_to(text_data=json.dumps(validate_face_payload()))


def successful_analysis_result():
    return {
        "face_detected": True,
        "concentration_level": "high",
        "concentration_score": 8,
        "message": "ok",
        "timestamp": "now",
        "analysis": {"head_pose_ok": True},
        "face_position": {},
        "recommendations": [],
        "metrics": {"gaze_ratio": 1.0, "drowsy_state": 0.2},
        "engagement": {"video_attentive": True, "inattention_duration": 0.0},
    }


def quality_result(*, blurry=False, low_light=False, blur_score=250.0, brightness_score=120.0):
    return {
        "blurry": blurry,
        "low_light": low_light,
        "blur_score": blur_score,
        "brightness_score": brightness_score,
        "contrast_score": 50.0,
    }


@pytest.mark.anyio
class TestFaceDetectionConsumerSecurity:
    async def test_unauthenticated_connection_is_rejected(self):
        communicator = communicator_for_user()
        connected, _ = await communicator.connect()

        assert connected is False

    async def test_authenticated_connection_is_accepted(self, user):
        communicator = await connect_authenticated(user)

        await communicator.disconnect()

    async def test_oversized_frame_is_rejected(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "MAX_FRAME_BASE64_CHARS", 16)
        communicator = await connect_authenticated(user)

        await communicator.send_json_to({
            "type": "validate_face",
            "face": {"x": 0, "y": 0, "width": 1, "height": 1},
            "frame": {"width": 1, "height": 1},
            "frame_base64": "a" * 17,
        })

        response = await communicator.receive_json_from(timeout=1)
        assert_safe_error_response(response)
        await communicator.wait(timeout=1)

    async def test_invalid_json_returns_sanitized_error(self, user):
        communicator = await connect_authenticated(user)

        await communicator.send_to(text_data='{"type": "validate_face", "bad": ')

        response = await communicator.receive_json_from(timeout=1)
        assert_safe_error_response(response)
        await communicator.disconnect()

    async def test_invalid_base64_returns_sanitized_error(self, user):
        communicator = await connect_authenticated(user)

        await communicator.send_json_to({
            "type": "validate_face",
            "face": {"x": 0, "y": 0, "width": 1, "height": 1},
            "frame": {"width": 1, "height": 1},
            "frame_base64": "this-is-not-valid-base64!",
        })

        response = await communicator.receive_json_from(timeout=1)
        assert_safe_error_response(response)
        await communicator.disconnect()

    async def test_cv_inference_exception_returns_sanitized_error(self, user, caplog):
        communicator = await connect_authenticated(user)
        internal_error = RuntimeError("secret internal path C:\\service\\model.py")

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", side_effect=internal_error),
        ):
            await send_validate_face(communicator)

            response = await communicator.receive_json_from(timeout=1)

        assert_safe_error_response(response)
        assert "secret internal path" in caplog.text
        assert "secret internal path" not in json.dumps(response)
        await communicator.disconnect()

    async def test_valid_decoded_image_is_accepted(self, user):
        communicator = await connect_authenticated(user)
        result = successful_analysis_result()

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(1280, 720)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=result) as analyze_mock,
        ):
            await send_validate_face(communicator)
            response = await communicator.receive_json_from(timeout=1)

        assert response["type"] == "validation_result"
        assert response["result"]["face_detected"] is True
        analyze_mock.assert_called_once()
        await communicator.disconnect()

    async def test_high_frequency_frames_only_process_bounded_count(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "FRAME_PROCESSING_INTERVAL_SECONDS", 0.5)
        monkeypatch.setattr(FaceDetectionConsumer, "_now", lambda self: 100.0)
        communicator = await connect_authenticated(user)
        result = successful_analysis_result()

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=result) as analyze_mock,
        ):
            responses = []
            for _ in range(5):
                await send_validate_face(communicator)
                responses.append(await communicator.receive_json_from(timeout=1))

        assert analyze_mock.call_count == 1
        assert responses[0]["type"] == "validation_result"
        assert responses[0]["result"]["face_detected"] is True
        assert [response["result"] for response in responses[1:]] == [FRAME_SKIPPED_RESULT] * 4
        await communicator.disconnect()

    async def test_skipped_frames_do_not_call_face_detection_or_decode(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "_now", lambda self: 100.0)
        communicator = await connect_authenticated(user)
        result = successful_analysis_result()

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)) as imdecode_mock,
            patch("apps.websocket.consumers.analyze_face_attention", return_value=result) as analyze_mock,
        ):
            await send_validate_face(communicator)
            processed_response = await communicator.receive_json_from(timeout=1)
            await send_validate_face(communicator)
            skipped_response = await communicator.receive_json_from(timeout=1)

        assert processed_response["result"]["face_detected"] is True
        assert skipped_response["result"] == FRAME_SKIPPED_RESULT
        assert imdecode_mock.call_count == 1
        assert analyze_mock.call_count == 1
        await communicator.disconnect()

    async def test_processed_frames_still_return_normal_validation_response(self, user, monkeypatch):
        clock_values = iter([100.0, 100.6])
        monkeypatch.setattr(FaceDetectionConsumer, "_now", lambda self: next(clock_values))
        communicator = await connect_authenticated(user)
        result = successful_analysis_result()

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=result) as analyze_mock,
        ):
            await send_validate_face(communicator)
            first_response = await communicator.receive_json_from(timeout=1)
            await send_validate_face(communicator)
            second_response = await communicator.receive_json_from(timeout=1)

        for response in [first_response, second_response]:
            assert response["type"] == "validation_result"
            assert response["result"]["face_detected"] is True
            assert response["result"]["concentration_level"] == "high"
            assert response["result"]["metrics"] == result["metrics"]
            assert response["result"]["engagement"] == result["engagement"]
            assert response["result"]["feedback"]["show_recommendations"] is True
        assert analyze_mock.call_count == 2
        await communicator.disconnect()

    async def test_normal_frame_passes_quality(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "FRAME_PROCESSING_INTERVAL_SECONDS", 0)
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=successful_analysis_result()),
            patch(
                "apps.websocket.consumers.FaceDetectionConsumer._assess_frame_quality",
                return_value=quality_result(),
            ),
        ):
            await send_validate_face(communicator)
            response = await communicator.receive_json_from(timeout=1)

        assert response["result"]["quality"]["blurry"] is False
        assert response["result"]["quality"]["low_light"] is False
        assert response["result"]["analysis"]["confidence"] == 1.0
        assert response["result"]["concentration_level"] == "high"
        await communicator.disconnect()

    async def test_blurry_frame_is_flagged_without_hard_alert(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "FRAME_PROCESSING_INTERVAL_SECONDS", 0)
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=successful_analysis_result()),
            patch(
                "apps.websocket.consumers.FaceDetectionConsumer._assess_frame_quality",
                return_value=quality_result(blurry=True, blur_score=12.3),
            ),
        ):
            await send_validate_face(communicator)
            response = await communicator.receive_json_from(timeout=1)

        assert response["result"]["quality"]["blurry"] is True
        assert response["result"]["quality"]["warning_triggered"] is False
        assert response["result"]["analysis"]["confidence"] == 0.5
        assert response["result"]["concentration_level"] == "high"
        assert response["result"]["feedback"]["action_required"] is False
        await communicator.disconnect()

    async def test_dark_frame_is_flagged(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "FRAME_PROCESSING_INTERVAL_SECONDS", 0)
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=successful_analysis_result()),
            patch(
                "apps.websocket.consumers.FaceDetectionConsumer._assess_frame_quality",
                return_value=quality_result(low_light=True, brightness_score=18.0),
            ),
        ):
            await send_validate_face(communicator)
            response = await communicator.receive_json_from(timeout=1)

        assert response["result"]["quality"]["low_light"] is True
        assert response["result"]["quality"]["brightness_score"] == 18.0
        assert response["result"]["analysis"]["confidence"] == 0.5
        await communicator.disconnect()

    async def test_repeated_blurry_frames_trigger_warning(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "FRAME_PROCESSING_INTERVAL_SECONDS", 0)
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=successful_analysis_result()),
            patch(
                "apps.websocket.consumers.FaceDetectionConsumer._assess_frame_quality",
                return_value=quality_result(blurry=True, blur_score=10.0),
            ),
        ):
            responses = []
            for _ in range(3):
                await send_validate_face(communicator)
                responses.append(await communicator.receive_json_from(timeout=1))

        assert responses[0]["result"]["quality"]["warning_triggered"] is False
        assert responses[1]["result"]["quality"]["warning_triggered"] is False
        assert responses[2]["result"]["quality"]["warning_triggered"] is True
        assert responses[2]["result"]["concentration_level"] == "low"
        assert responses[2]["result"]["concentration_score"] == 3
        assert responses[2]["result"]["feedback"]["action_required"] is True
        await communicator.disconnect()

    async def test_repeated_dark_frames_trigger_warning(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "FRAME_PROCESSING_INTERVAL_SECONDS", 0)
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=successful_analysis_result()),
            patch(
                "apps.websocket.consumers.FaceDetectionConsumer._assess_frame_quality",
                return_value=quality_result(low_light=True, brightness_score=20.0),
            ),
        ):
            responses = []
            for _ in range(3):
                await send_validate_face(communicator)
                responses.append(await communicator.receive_json_from(timeout=1))

        assert responses[2]["result"]["quality"]["warning_triggered"] is True
        assert responses[2]["result"]["quality"]["low_light"] is True
        assert responses[2]["result"]["concentration_level"] == "low"
        assert responses[2]["result"]["engagement"]["trigger_feedback"] is True
        await communicator.disconnect()

    async def test_overlapping_inference_is_prevented(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "_now", lambda self: 100.0)
        consumer = FaceDetectionConsumer()
        consumer.user_id = user.id
        sent_messages = []

        async def capture_send(*, text_data=None, bytes_data=None, close=False):
            if text_data is not None:
                sent_messages.append(json.loads(text_data))

        def slow_analysis(face_analysis_data):
            import time

            time.sleep(0.05)
            return successful_analysis_result()

        consumer.send = capture_send

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", side_effect=slow_analysis) as analyze_mock,
        ):
            first_task = asyncio.create_task(consumer.handle_validate_face(validate_face_payload()))
            await asyncio.sleep(0.01)
            await consumer.handle_validate_face(validate_face_payload())
            await first_task

        assert analyze_mock.call_count == 1
        assert len(sent_messages) == 2
        assert sent_messages[0]["result"] == FRAME_SKIPPED_RESULT
        assert sent_messages[1]["result"]["face_detected"] is True
        assert consumer.inference_running is False

    async def test_oversized_decoded_width_is_rejected_before_face_detection(self, user):
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(1281, 1)),
            patch("apps.websocket.consumers.analyze_face_attention") as analyze_mock,
        ):
            await send_validate_face(communicator)
            response = await communicator.receive_json_from(timeout=1)

        assert_frame_too_large_response(response)
        analyze_mock.assert_not_called()
        await communicator.disconnect()

    async def test_oversized_decoded_height_is_rejected_before_face_detection(self, user):
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(1, 721)),
            patch("apps.websocket.consumers.analyze_face_attention") as analyze_mock,
        ):
            await send_validate_face(communicator)
            response = await communicator.receive_json_from(timeout=1)

        assert_frame_too_large_response(response)
        analyze_mock.assert_not_called()
        await communicator.disconnect()

    async def test_oversized_decoded_total_pixels_is_rejected_before_face_detection(
        self,
        user,
        monkeypatch,
    ):
        monkeypatch.setattr(FaceDetectionConsumer, "MAX_DECODED_FRAME_WIDTH", 2000)
        monkeypatch.setattr(FaceDetectionConsumer, "MAX_DECODED_FRAME_HEIGHT", 2000)
        monkeypatch.setattr(FaceDetectionConsumer, "MAX_DECODED_FRAME_PIXELS", 100)
        communicator = await connect_authenticated(user)

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(11, 10)),
            patch("apps.websocket.consumers.analyze_face_attention") as analyze_mock,
        ):
            await send_validate_face(communicator)
            response = await communicator.receive_json_from(timeout=1)

        assert_frame_too_large_response(response)
        analyze_mock.assert_not_called()
        await communicator.disconnect()

    async def test_receive_exception_returns_sanitized_error(self, user, monkeypatch, caplog):
        async def raise_receive_error(self):
            raise RuntimeError("secret receive failure C:\\tmp\\receive.py")

        monkeypatch.setattr(FaceDetectionConsumer, "handle_get_stats", raise_receive_error)
        communicator = await connect_authenticated(user)

        await communicator.send_json_to({"type": "get_stats"})

        response = await communicator.receive_json_from(timeout=1)
        assert_safe_error_response(response)
        assert "secret receive failure" in caplog.text
        assert "secret receive failure" not in json.dumps(response)
        await communicator.disconnect()

    async def test_endcall_exception_returns_sanitized_error(self, user, monkeypatch, caplog):
        def raise_endcall_error(self, metrics):
            raise RuntimeError("secret endcall failure C:\\tmp\\endcall.py")

        monkeypatch.setattr(FaceDetectionConsumer, "_build_session_summary", raise_endcall_error)
        communicator = await connect_authenticated(user)

        await communicator.send_json_to({"type": "endcall"})

        response = await communicator.receive_json_from(timeout=1)
        assert_safe_error_response(response)
        assert "secret endcall failure" in caplog.text
        assert "secret endcall failure" not in json.dumps(response)
        await communicator.disconnect()

    async def test_rate_limit_closes_excessive_messages(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "RATE_LIMIT_MESSAGES", 2)
        monkeypatch.setattr(FaceDetectionConsumer, "RATE_LIMIT_WINDOW_SECONDS", 60)
        communicator = await connect_authenticated(user)

        await communicator.send_json_to({"type": "ping"})
        pong = await communicator.receive_json_from(timeout=1)
        assert pong["type"] == "pong"

        await communicator.send_json_to({"type": "ping"})
        pong = await communicator.receive_json_from(timeout=1)
        assert pong["type"] == "pong"

        await communicator.send_json_to({"type": "ping"})
        response = await communicator.receive_json_from(timeout=1)
        assert_safe_error_response(response)
        await communicator.wait(timeout=1)

    async def test_metrics_storage_does_not_grow_unbounded(self, user, monkeypatch):
        monkeypatch.setattr(FaceDetectionConsumer, "MAX_SESSION_METRIC_SAMPLES", 2)
        monkeypatch.setattr(FaceDetectionConsumer, "FRAME_PROCESSING_INTERVAL_SECONDS", 0)
        communicator = await connect_authenticated(user)

        result = successful_analysis_result()

        with (
            patch("apps.websocket.consumers.cv2.imdecode", return_value=FakeDecodedFrame(640, 480)),
            patch("apps.websocket.consumers.analyze_face_attention", return_value=result),
        ):
            for _ in range(4):
                await send_validate_face(communicator)
                response = await communicator.receive_json_from(timeout=1)
                assert response["type"] == "validation_result"

        await communicator.send_json_to({"type": "get_stats"})
        stats_response = await communicator.receive_json_from(timeout=1)
        assert stats_response["stats"]["session_info"]["stored_metric_samples"] == 2
        assert stats_response["stats"]["session_info"]["metrics_collected"] == 4
        await communicator.disconnect()
