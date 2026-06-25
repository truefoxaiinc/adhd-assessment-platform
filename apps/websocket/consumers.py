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
        self.last_attention_state = "idle_distracted"

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
        self.last_attention_state = "idle_distracted"

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

            session_summary = self._build_session_summary(self.session_metrics)

            await self.send(text_data=json.dumps({
                'type': 'endcall_processed',
                'session_id': self.session_id,
                'user_id': self.user_id,
                'metrics_count': len(self.session_metrics),
                'session_summary': session_summary,
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
                'expected_fps': 30,
                'frame_time_seconds': self.frame_count / 30.0,
                'gaze_history': self.gaze_history,
                'blink_history': self.blink_history,
                'score_history': self.score_history,
                'inattention_start': self.inattention_start,
                'mode': mode,
                'pdf_is_visible': pdf_is_visible,
                'is_assessment': is_assessment,
                'eye': data.get('eye', {}) or {},
                'last_attention_state': self.last_attention_state,
            }

            if self.validation_settings.get('custom_tolerance'):
                face_analysis_data['custom_settings'] = self.validation_settings['custom_tolerance']

            result = await asyncio.get_event_loop().run_in_executor(
                None, analyze_face_attention_with_models, face_analysis_data
            )

            if 'inattention_start' in result:
                self.inattention_start = result['inattention_start']
            self.last_attention_state = result.get('engagement', {}).get(
                'state',
                self.last_attention_state,
            )

            # Track every assessment frame. No-face/invalid frames must count
            # as zero; otherwise the final score can remain high because only
            # successful face frames are averaged.
            if self.user_id:
                analysis = result.get('analysis', {}) or {}
                metrics = result.get('metrics', {}) or {}
                engagement = result.get('engagement', {}) or {}
                self.session_metrics.append({
                    'concentration_score': result.get('concentration_score', 0),
                    'gaze_ratio': metrics.get('gaze_ratio', 0.0),
                    'inattention_duration': engagement.get('inattention_duration', 0.0),
                    'drowsy_state': metrics.get('drowsy_state', 0.8),
                    'face_detected': result.get('face_detected', False),
                    'video_attentive': engagement.get('video_attentive', False),
                    'eyes_closed': analysis.get('eyes_closed', False),
                    'yawning': analysis.get('yawning', False),
                    'gaze_state': analysis.get('gaze_state') or metrics.get('gaze_state') or '',
                    'head_pose_ok': analysis.get('head_pose_ok', False),
                    'low_light': analysis.get('low_light', False),
                    'brightness_score': metrics.get('brightness_score', 0.0),
                    'pitch': metrics.get('pitch', 0.0),
                    'yaw': metrics.get('yaw', 0.0),
                    'roll': metrics.get('roll', 0.0),
                    'blink_ratio': metrics.get('blink_ratio', 0.0),
                    'yawn_distance': metrics.get('yawn_distance', 0.0),
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
                    'validation_passed': (
                        result.get('face_detected', False)
                        and result.get('concentration_level', '') in ['high', 'medium']
                    ),
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

    def _build_session_summary(self, metrics):
        total = len(metrics)
        if total == 0:
            return {}

        def pct(key):
            return round((sum(1 for m in metrics if m.get(key)) / total) * 100, 2)

        avg_concentration = sum(m.get('concentration_score', 0) for m in metrics) / total
        avg_gaze_ratio = sum(m.get('gaze_ratio', 0.0) for m in metrics) / total
        max_inattention = max((m.get('inattention_duration', 0.0) for m in metrics), default=0.0)
        side_gaze_frames = sum(1 for m in metrics if m.get('gaze_state') in ['LEFT', 'RIGHT'])
        low_light_frames = sum(1 for m in metrics if m.get('low_light'))
        eyes_closed_frames = sum(1 for m in metrics if m.get('eyes_closed'))
        yawning_frames = sum(1 for m in metrics if m.get('yawning'))
        drowsy_frames = sum(1 for m in metrics if m.get('drowsy_state', 0.2) != 0.2)

        return {
            'total_frames': total,
            'avg_concentration_score': round(avg_concentration, 2),
            'final_attention_score_percent': round((avg_concentration / 8.0) * 100, 2),
            'avg_gaze_ratio': round(avg_gaze_ratio, 4),
            'max_inattention_duration': round(max_inattention, 2),
            'face_detection_rate': pct('face_detected'),
            'attention_engagement_rate': pct('video_attentive'),
            'head_stability_rate': pct('head_pose_ok'),
            'eye_closed_rate': round((eyes_closed_frames / total) * 100, 2),
            'yawning_rate': round((yawning_frames / total) * 100, 2),
            'drowsy_rate': round((drowsy_frames / total) * 100, 2),
            'side_gaze_rate': round((side_gaze_frames / total) * 100, 2),
            'low_light_rate': round((low_light_frames / total) * 100, 2),
            'eyes_closed_frames': eyes_closed_frames,
            'yawning_frames': yawning_frames,
            'side_gaze_frames': side_gaze_frames,
            'low_light_frames': low_light_frames,
        }

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
        summary = self._build_session_summary(metrics)
        attention_engagement_rate = summary.get('attention_engagement_rate', 0.0)
        for m in metrics:
            FaceAttentionSession.objects.create(
                user_id=user_id,
                session_id=session_id,
                concentration_score=m['concentration_score'],
                gaze_ratio_avg=m['gaze_ratio'],
                inattention_duration=m['inattention_duration'],
                drowsy_state=m['drowsy_state'],
                face_detected=m.get('face_detected', False),
                video_attentive=m.get('video_attentive', False),
                eyes_closed=m.get('eyes_closed', False),
                yawning=m.get('yawning', False),
                gaze_state=m.get('gaze_state') or '',
                head_pose_ok=m.get('head_pose_ok', False),
                low_light=m.get('low_light', False),
                brightness_score=m.get('brightness_score', 0.0),
                pitch=m.get('pitch', 0.0),
                yaw=m.get('yaw', 0.0),
                roll=m.get('roll', 0.0),
                blink_ratio=m.get('blink_ratio', 0.0),
                yawn_distance=m.get('yawn_distance', 0.0),
                attention_engagement_rate=attention_engagement_rate,
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
