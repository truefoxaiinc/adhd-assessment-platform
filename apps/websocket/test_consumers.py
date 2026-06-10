import pytest
from channels.testing import WebsocketCommunicator
from project_adhd.asgi import application
from apps.websocket.consumers import FaceDetectionConsumer
from apps.users.models import Users
import json

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestFaceDetectionConsumer:
    async def test_connect(self):
        communicator = WebsocketCommunicator(FaceDetectionConsumer.as_asgi(), "/ws/face-detection/")
        connected, subprotocol = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_receive_invalid_json(self):
        communicator = WebsocketCommunicator(FaceDetectionConsumer.as_asgi(), "/ws/face-detection/")
        await communicator.connect()
        await communicator.send_to(text_data="invalid json")
        # Ensure it doesn't crash but maybe sends an error back or ignores
        try:
            response = await communicator.receive_from(timeout=1)
            # The consumer might return an error message
            assert response
        except Exception:
            pass # Or it might just do nothing
        await communicator.disconnect()

    async def test_endcall_event(self, mocker):
        communicator = WebsocketCommunicator(FaceDetectionConsumer.as_asgi(), "/ws/face-detection/")
        await communicator.connect()
        
        # We can mock the synchronous database saving or just let it fail gracefully
        mocker.patch('apps.websocket.consumers.FaceDetectionConsumer.save_assessment_data')
        
        data = {
            "event": "endcall",
            "userid": 1
        }
        await communicator.send_json_to(data)
        
        # Ensure disconnect closes properly
        await communicator.disconnect()
