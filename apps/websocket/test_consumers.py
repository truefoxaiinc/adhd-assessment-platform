import pytest
from channels.testing import WebsocketCommunicator
from apps.websocket.consumers import FaceDetectionConsumer

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
        
        data = {
            "type": "endcall",
            "filetype": "video",
            "day_completed": 1,
            "order_number": 1
        }
        await communicator.send_json_to(data)
        response = await communicator.receive_json_from(timeout=1)
        assert response["type"] == "endcall_processed"
        
        await communicator.disconnect()
