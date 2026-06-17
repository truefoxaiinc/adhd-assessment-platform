import json
import asyncio
import base64
import cv2
import numpy as np
import uuid
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.websocket.face_detection_ai.face_detection_utils_v2 import (
    analyze_face_attention_with_models,
)


class FaceDetectionConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frame_width = 640
        self.frame_height = 480
        self.validation_settings = {
            'strict_mode': False,
            'custom_tolerance': {
                'center': 0.15,
                'size_min': 0.08,
                'edge_margin': 0.05
            },
            'batch_validation': False
        }
        self.session_id = None
        self.session_metrics = []
        self.user_id = None
        import collections
        self.gaze_history = collections.deque()
        self.blink_history = collections.deque()
        self.score_history = collections.deque(maxlen=5)
        self.inattention_start = None
        self.frame_count = 0
        self.last_response_data = None
        self.assessment_score_saved = False

    async def connect(self):
        # NO MODEL IMPORTS - safe user ID extraction only
        scope_user = self.scope.get("user")
        self.user_id = getattr(scope_user, 'id', None) if scope_user and scope_user.is_authenticated else None
        
        self.session_id = str(uuid.uuid4())[:8]
        self.session_metrics = []
        self.gaze_history.clear()
        self.blink_history.clear()
        self.score_history.clear()
        self.inattention_start = None
        self.frame_count = 0
        self.last_response_data = None
        self.assessment_score_saved = False

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket ready - Send frame as base64 for full analysis',
            'session_id': self.session_id,
            'user_id': self.user_id,
            'auth_format': 'ws://host/ws/face-detection/?token=access_token',
            'timestamp': datetime.now().isoformat(),
            'expected_format': {
                'type': 'validate_face',
                'frame_base64': 'base64_encoded_image',
                'face': {'x': 'int', 'y': 'int', 'width': 'int', 'height': 'int'},
                'frame': {'width': 'int', 'height': 'int'},
                'is_assessment': False
            },
            'endcall_format': {
                'type': 'endcall',
                'filetype': 'video|file',
                'day_completed': '1|2|3|... (int day number)',
                'order_number': 'int'
            }
        }))

    async def disconnect(self, close_code):
        if self.user_id and self.session_metrics:
            await self._save_assessment_score()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'endcall':
                await self.handle_endcall(data)
                return

            if message_type == 'validate_face':
                await self.handle_validate_face(data)
            elif message_type == 'update_settings':
                await self.handle_update_settings(data)
            elif message_type == 'get_guidelines':
                await self.handle_get_guidelines()
            elif message_type == 'get_stats':
                await self.handle_get_stats()
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
            else:
                await self.send_error(f'Unknown message type: {message_type}')

        except json.JSONDecodeError as e:
            await self.send_error(f'Invalid JSON format: {str(e)}')
        except Exception as e:
            await self.send_error(f'Unexpected error: {str(e)}')

    async def handle_endcall(self, data):
        try:
            # 🔥 Extract progress tracking parameters from endcall message
            filetype = data.get('filetype')
            day_completed = data.get('day_completed')
            order_number = data.get('order_number')

            # 🔥 FIXED: Async-safe ProgressTrackerActions call
            progress_updated = False
            if self.user_id and filetype and day_completed is not None and order_number is not None:
                success = await self._update_learning_progress_async(
                    self.user_id, filetype, day_completed, order_number
                )
                progress_updated = success

            # Save face attention assessment if metrics exist
            if self.user_id and self.session_metrics:
                await self._save_assessment_score()

            await self.send(text_data=json.dumps({
                'type': 'endcall_processed',
                'session_id': self.session_id,
                'user_id': self.user_id,
                'metrics_count': len(self.session_metrics),
                'filetype': filetype,
                'day_completed': day_completed,
                'order_number': order_number,
                'progress_updated': progress_updated,
                'message': 'Session ended successfully',
                'timestamp': datetime.now().isoformat()
            }))
            await self.close()
            
        except Exception as e:
            await self.send_error(f'Endcall processing error: {str(e)}')

    # 🔥 NEW: Async wrapper for sync DB operation (FIXES SynchronousOnlyOperation)
    @database_sync_to_async
    def _update_learning_progress_sync(self, user_id, filetype, day_completed, order_number):
        """Sync wrapper for ProgressTrackerActions - SAFE for async context"""
        from apps.users.models import Users
        from apps.progresstracker.services.track_services import ProgressTrackerActions
        
        try:
            user_instance = Users.objects.get(id=user_id)
            return ProgressTrackerActions.update_learning_progress(
                user_instance, filetype, day_completed, order_number
            )
        except Users.DoesNotExist:
            return False
        except Exception:
            return False

    async def _update_learning_progress_async(self, user_id, filetype, day_completed, order_number):
        """Async wrapper for sync progress update"""
        return await self._update_learning_progress_sync(user_id, filetype, day_completed, order_number)

    async def handle_validate_face(self, data):
        try:
            self.frame_count += 1

            face_data = data.get('face')
            frame_data = data.get('frame', {'width': self.frame_width, 'height': self.frame_height})
            frame_base64 = data.get('frame_base64')
            is_assessment = data.get('is_assessment', False)
            mode = data.get('mode', 'video')
            pdf_is_visible = data.get('pdf_is_visible', False)

            if not face_data:
                await self.send_error('Face data is required')
                return

            if not frame_base64:
                await self.send_error('frame_base64 is required for full analysis')
                return

            # Decode frame
            frame_bytes = base64.b64decode(frame_base64)
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame_bgr is None:
                await self.send_error('Invalid frame_base64 data')
                return

            face_analysis_data = {
                'x': face_data.get('x', 0),
                'y': face_data.get('y', 0),
                'width': face_data.get('width', 0),
                'height': face_data.get('height', 0),
                'frame_width': frame_data.get('width', self.frame_width),
                'frame_height': frame_data.get('height', self.frame_height),
                'frame_bgr': frame_bgr,
                'gaze_history': self.gaze_history,
                'blink_history': self.blink_history,
                'score_history': self.score_history,
                'inattention_start': self.inattention_start,
                'mode': mode,
                'pdf_is_visible': pdf_is_visible,
            }

            if self.validation_settings.get('custom_tolerance'):
                face_analysis_data['custom_settings'] = self.validation_settings['custom_tolerance']

            result = await asyncio.get_event_loop().run_in_executor(
                None, analyze_face_attention_with_models, face_analysis_data
            )

            if 'inattention_start' in result:
                self.inattention_start = result['inattention_start']

            # Track metrics if user_id exists & face detected
            if result.get('face_detected') and self.user_id:
                self.session_metrics.append({
                    'concentration_score': result['concentration_score'],
                    'gaze_ratio': result['metrics'].get('gaze_ratio', 1.0),
                    'inattention_duration': result['engagement'].get('inattention_duration', 0.0),
                    'drowsy_state': result['metrics'].get('drowsy_state', 0.2)
                })

            response_data = {
                'type': 'validation_result',
                'result': {
                    'face_detected': result.get('face_detected', False),
                    'concentration_level': result.get('concentration_level', 'error'),
                    'concentration_score': result.get('concentration_score', 0),
                    'message': result.get('message', ''),
                    'timestamp': result.get('timestamp', ''),
                    'analysis': result.get('analysis', {}),
                    'face_position': result.get('face_position', {}),
                    'recommendations': result.get('recommendations', []),
                    'validation_passed': result.get('concentration_level', '') in ['high', 'medium'],
                    'metrics': result.get('metrics', {}),
                    'engagement': result.get('engagement', {})
                },
                'session_metrics_count': len(self.session_metrics),
                'user_id': self.user_id,
                'timestamp': datetime.now().isoformat()
            }

            if not is_assessment:
                response_data['result']['feedback'] = {
                    'show_recommendations': True,
                    'alert_level': result.get('concentration_level', 'low'),
                    'action_required': result.get('concentration_level', '') == 'low',
                    'inattention_duration': result['engagement'].get('inattention_duration', 0)
                }

            self.last_response_data = response_data
            await self.send(text_data=json.dumps(response_data, default=str))

        except Exception as e:
            await self.send_error(f'Face validation error: {str(e)}')

    async def handle_update_settings(self, data):
        try:
            settings = data.get('settings', {})
            self.validation_settings.update(settings)
            await self.send(text_data=json.dumps({
                'type': 'settings_updated',
                'settings': self.validation_settings,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            await self.send_error(f'Settings update error: {str(e)}')

    async def handle_get_guidelines(self):
        try:
            guidelines = {
                'optimal_position': {
                    'face_center_x': self.frame_width // 2,
                    'face_center_y': self.frame_height // 2,
                    'tolerance_x': self.frame_width * 0.25,
                    'tolerance_y': self.frame_height * 0.25
                },
                'face_size': {
                    'min_width': int(self.frame_width * 0.15),
                    'max_width': int(self.frame_width * 0.6),
                    'recommended_width': int(self.frame_width * 0.25)
                },
                'positioning_tips': [
                    'Center your face in the frame',
                    'Maintain consistent distance from camera',
                    'Send frame as base64 for accurate analysis',
                    'Good lighting helps with detection'
                ]
            }
            await self.send(text_data=json.dumps({
                'type': 'positioning_guidelines',
                'guidelines': guidelines,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            await self.send_error(f'Guidelines retrieval error: {str(e)}')

    async def handle_get_stats(self):
        try:
            stats = {
                'current_frame_dimensions': {
                    'width': self.frame_width,
                    'height': self.frame_height
                },
                'validation_settings': self.validation_settings,
                'session_info': {
                    'session_id': self.session_id,
                    'metrics_collected': len(self.session_metrics),
                    'user_id': self.user_id
                },
                'supported_features': [
                    'Real-time face validation (base64 frames)',
                    'Yawn detection', 'Gaze tracking', 'Head pose estimation',
                    'Blink detection', 'Reading pattern recognition',
                    'AI Assessment Score (endcall)'
                ]
            }
            await self.send(text_data=json.dumps({
                'type': 'detection_stats',
                'stats': stats,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            await self.send_error(f'Stats retrieval error: {str(e)}')

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }))

    # 🔥 NO TOP-LEVEL MODEL IMPORTS - LAZY LOADING ONLY
    @database_sync_to_async
    def _create_sessions_sync(self, user_id, session_id, metrics):
        """CHANGE 'apps.yourapp.models' to your actual app path"""
        from apps.progresstracker.models import FaceAttentionSession  # UPDATE THIS PATH
        for m in metrics:
            FaceAttentionSession.objects.create(
                user_id=user_id,
                session_id=session_id,
                concentration_score=m['concentration_score'],
                gaze_ratio_avg=m['gaze_ratio'],
                inattention_duration=m['inattention_duration'],
                drowsy_state=m['drowsy_state']
            )

    @database_sync_to_async
    def _update_user_score_sync(self, user_id, final_score):
        """CHANGE 'apps.yourapp.models' to your actual app path"""
        from apps.users.models import Users  # UPDATE THIS PATH
        user = Users.objects.get(id=user_id)
        user.ai_assessment_score = final_score
        user.save(update_fields=['ai_assessment_score'])
        return user.ai_assessment_score

    async def _save_assessment_score(self):
        if self.assessment_score_saved or not self.user_id or not self.session_metrics:
            return

        avg_concentration = sum(m['concentration_score'] for m in self.session_metrics) / len(self.session_metrics)
        final_score = round((avg_concentration / 8.0) * 100, 2)

        await self._create_sessions_sync(self.user_id, self.session_id, self.session_metrics)
        await self._update_user_score_sync(self.user_id, final_score)
        self.assessment_score_saved = True
