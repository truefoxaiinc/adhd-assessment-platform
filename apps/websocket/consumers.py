import json
import asyncio
import base64
import binascii
import collections
import logging
import time
import cv2
import numpy as np
import uuid
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.websocket.services.face_analysis_service import analyze_face_attention
from apps.websocket.services.rate_limit_service import WebSocketRateLimiter


logger = logging.getLogger(__name__)


def extract_eye_data(payload):
    eye_data = dict(payload.get('eye', {}) or {})
    for key in (
        'left_eye_open_probability',
        'right_eye_open_probability',
        'left_open_probability',
        'right_open_probability',
        'leftEyeOpenProbability',
        'rightEyeOpenProbability',
        'eye_aspect_ratio',
        'eyeAspectRatio',
        'ear',
    ):
        if key in payload and key not in eye_data:
            eye_data[key] = payload.get(key)
    face_data = payload.get('face', {}) or {}
    for key in (
        'left_eye_open_probability',
        'right_eye_open_probability',
        'left_open_probability',
        'right_open_probability',
        'leftEyeOpenProbability',
        'rightEyeOpenProbability',
        'eye_aspect_ratio',
        'eyeAspectRatio',
        'ear',
    ):
        if key in face_data and key not in eye_data:
            eye_data[key] = face_data.get(key)
    return eye_data


class FaceDetectionConsumer(AsyncWebsocketConsumer):
    SAFE_ERROR_CODE = "FACE_VALIDATION_FAILED"
    SAFE_ERROR_MESSAGE = "Unable to process frame safely"
    FRAME_TOO_LARGE_ERROR_CODE = "FRAME_TOO_LARGE"
    FRAME_TOO_LARGE_ERROR_MESSAGE = "Frame is too large"
    MAX_TEXT_MESSAGE_BYTES = 1_500_000
    MAX_FRAME_BASE64_CHARS = 1_400_000
    MAX_DECODED_FRAME_WIDTH = 1280
    MAX_DECODED_FRAME_HEIGHT = 720
    MAX_DECODED_FRAME_PIXELS = 921_600
    FRAME_PROCESSING_INTERVAL_SECONDS = 0.5
    BLUR_VARIANCE_THRESHOLD = 100.0
    LOW_LIGHT_BRIGHTNESS_THRESHOLD = 60.0
    LOW_LIGHT_CONTRAST_THRESHOLD = 25.0
    BAD_QUALITY_WARNING_FRAME_THRESHOLD = 3
    TEMPORAL_WINDOW_SIZE = 5
    TEMPORAL_BAD_FRAME_THRESHOLD = 3
    GAZE_RATIO_MIN_RELIABLE = 0.2
    GAZE_RATIO_MAX_RELIABLE = 8.0
    UI_ALERT_NOISY_REASON_THRESHOLD = 2
    RATE_LIMIT_MESSAGES = 30
    RATE_LIMIT_WINDOW_SECONDS = 10
    MAX_SESSION_METRIC_SAMPLES = 300
    CLOSE_CODE_UNAUTHORIZED = 4401
    CLOSE_CODE_POLICY_VIOLATION = 4408
    CLOSE_CODE_RATE_LIMITED = 4429

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
        self.session_started_at = None
        self.session_started_monotonic = None
        self.session_metrics = collections.deque(maxlen=self.MAX_SESSION_METRIC_SAMPLES)
        self.session_metric_totals = self._new_metric_totals()
        self.user_id = None
        self.gaze_history = collections.deque()
        self.blink_history = collections.deque()
        self.score_history = collections.deque(maxlen=5)
        self.inattention_start = None
        self.frame_count = 0
        self.last_response_data = None
        self.assessment_score_saved = False
        self.last_attention_state = "idle_distracted"
        self.last_processed_frame_at = None
        self.inference_running = False
        self.bad_quality_frame_count = 0
        self.temporal_window = collections.deque(maxlen=self.TEMPORAL_WINDOW_SIZE)
        self.ui_warning_reason = None
        self.ui_warning_count = 0
        self.rate_limiter = WebSocketRateLimiter(
            self.RATE_LIMIT_MESSAGES,
            self.RATE_LIMIT_WINDOW_SECONDS,
        )

    async def connect(self):
        scope_user = self.scope.get("user")
        if not scope_user or not scope_user.is_authenticated:
            await self.close(code=self.CLOSE_CODE_UNAUTHORIZED)
            return

        self.user_id = getattr(scope_user, 'id', None)
        
        self.session_id = str(uuid.uuid4())[:8]
        self.session_started_at = time.time()
        self.session_started_monotonic = self._now()
        self.session_metrics = collections.deque(maxlen=self.MAX_SESSION_METRIC_SAMPLES)
        self.session_metric_totals = self._new_metric_totals()
        self.gaze_history.clear()
        self.blink_history.clear()
        self.score_history.clear()
        self.inattention_start = None
        self.frame_count = 0
        self.last_response_data = None
        self.assessment_score_saved = False
        self.last_attention_state = "idle_distracted"
        self.last_processed_frame_at = None
        self.inference_running = False
        self.bad_quality_frame_count = 0
        self.temporal_window = collections.deque(maxlen=self.TEMPORAL_WINDOW_SIZE)
        self.ui_warning_reason = None
        self.ui_warning_count = 0
        self.rate_limiter.clear()

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
        if self.user_id and self.session_metric_totals.get('total_frames', 0):
            await self._save_assessment_score()

    async def receive(self, text_data):
        try:
            if not await self._allow_message():
                logger.warning(
                    "WebSocket rate limit exceeded",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                await self.close(code=self.CLOSE_CODE_RATE_LIMITED)
                return

            if self._message_too_large(text_data):
                logger.warning(
                    "WebSocket message payload too large",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                await self.close(code=self.CLOSE_CODE_POLICY_VIOLATION)
                return

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
                logger.warning(
                    "Unknown WebSocket message type",
                    extra={
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                        "message_type": message_type,
                    },
                )
                await self.send_error()

        except json.JSONDecodeError:
            logger.exception(
                "Invalid WebSocket JSON payload",
                extra={"user_id": self.user_id, "session_id": self.session_id},
            )
            await self.send_error()
        except Exception:
            logger.exception(
                "Unexpected WebSocket receive error",
                extra={"user_id": self.user_id, "session_id": self.session_id},
            )
            await self.send_error()

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
            if self.user_id and self.session_metric_totals.get('total_frames', 0):
                await self._save_assessment_score()

            session_summary = self._build_session_summary(self.session_metrics)

            await self.send(text_data=json.dumps({
                'type': 'endcall_processed',
                'session_id': self.session_id,
                'user_id': self.user_id,
                'metrics_count': self.session_metric_totals.get('total_frames', 0),
                'session_summary': session_summary,
                'filetype': filetype,
                'day_completed': day_completed,
                'order_number': order_number,
                'progress_updated': progress_updated,
                'message': 'Session ended successfully',
                'timestamp': datetime.now().isoformat()
            }))
            await self.close()
            
        except Exception:
            logger.exception(
                "Endcall processing failed",
                extra={"user_id": self.user_id, "session_id": self.session_id},
            )
            await self.send_error()

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
        processing_started = False
        try:
            self.frame_count += 1

            face_data = data.get('face')
            frame_data = data.get('frame', {'width': self.frame_width, 'height': self.frame_height})
            frame_base64 = data.get('frame_base64')
            request_frame_id = data.get('frame_id')
            is_assessment = data.get('is_assessment', False)
            mode = data.get('mode', 'video')
            pdf_is_visible = data.get('pdf_is_visible', False)

            if not face_data:
                logger.warning(
                    "Face validation request missing face data",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                return

            if not frame_base64:
                logger.warning(
                    "Face validation request missing frame_base64",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                return

            if not isinstance(frame_base64, str):
                logger.warning(
                    "Face validation request frame_base64 is not a string",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                return

            if len(frame_base64) > self.MAX_FRAME_BASE64_CHARS:
                logger.warning(
                    "Face validation frame payload too large",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                await self.close(code=self.CLOSE_CODE_POLICY_VIOLATION)
                return

            frame_processing_started_at = self._now()
            if not self._should_process_frame(frame_processing_started_at):
                await self.send_frame_skipped(frame_id=request_frame_id)
                return

            self.inference_running = True
            processing_started = True
            self.last_processed_frame_at = frame_processing_started_at
            session_started_monotonic = self.session_started_monotonic or frame_processing_started_at
            frame_time_seconds = max(frame_processing_started_at - session_started_monotonic, 0.0)

            # Decode frame
            try:
                frame_bytes = base64.b64decode(frame_base64, validate=True)
            except (binascii.Error, ValueError):
                logger.exception(
                    "Invalid frame_base64 data",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                return

            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame_bgr is None:
                logger.warning(
                    "OpenCV could not decode frame_base64 data",
                    extra={"user_id": self.user_id, "session_id": self.session_id},
                )
                await self.send_error()
                return

            if self._decoded_frame_too_large(frame_bgr):
                frame_height, frame_width = frame_bgr.shape[:2]
                logger.warning(
                    "Decoded frame exceeds size limits",
                    extra={
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                        "frame_width": int(frame_width),
                        "frame_height": int(frame_height),
                        "frame_pixels": int(frame_width * frame_height),
                    },
                )
                await self.send_frame_too_large_error()
                return

            quality = self._assess_frame_quality(frame_bgr)
            quality_warning_triggered = self._record_frame_quality(quality)
            quality['warning_triggered'] = quality_warning_triggered

            face_analysis_data = {
                'x': face_data.get('x', 0),
                'y': face_data.get('y', 0),
                'width': face_data.get('width', 0),
                'height': face_data.get('height', 0),
                'confidence': face_data.get('confidence'),
                'face_timestamp_seconds': face_data.get('timestamp_seconds'),
                'face_frame_id': face_data.get('frame_id'),
                'frame_id': request_frame_id,
                'frame_width': frame_data.get('width', self.frame_width),
                'frame_height': frame_data.get('height', self.frame_height),
                'frame_bgr': frame_bgr,
                'expected_fps': 30,
                'frame_time_seconds': frame_time_seconds,
                'gaze_history': self.gaze_history,
                'blink_history': self.blink_history,
                'score_history': self.score_history,
                'inattention_start': self.inattention_start,
                'mode': mode,
                'pdf_is_visible': pdf_is_visible,
                'is_assessment': is_assessment,
                'eye': extract_eye_data(data),
                'last_attention_state': self.last_attention_state,
            }

            if self.validation_settings.get('custom_tolerance'):
                face_analysis_data['custom_settings'] = self.validation_settings['custom_tolerance']

            result = await asyncio.get_event_loop().run_in_executor(
                None, analyze_face_attention, face_analysis_data
            )
            self._apply_frame_quality(result, quality)
            self._apply_temporal_smoothing(result)
            self._apply_ui_alert_stability(result)

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
                self._record_session_metric({
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
                    'confidence': analysis.get('confidence', metrics.get('confidence', 0.0)),
                    'blurry': result.get('quality', {}).get('blurry', False),
                    'bad_frame': result.get('temporal', {}).get('warning_triggered', False),
                })

            response_data = {
                'type': 'validation_result',
                'frame_id': request_frame_id,
                'result': {
                    'frame_id': request_frame_id,
                    'face_detected': result.get('face_detected', False),
                    'concentration_level': result.get('concentration_level', 'error'),
                    'concentration_score': result.get('concentration_score', 0),
                    'message': result.get('message', ''),
                    'timestamp': result.get('timestamp', ''),
                    'analysis': result.get('analysis', {}),
                    'face_position': result.get('face_position', {}),
                    'recommendations': result.get('recommendations', []),
                    'quality': result.get('quality', {}),
                    'temporal': result.get('temporal', {}),
                    'validation_passed': (
                        result.get('face_detected', False)
                        and result.get('concentration_level', '') in ['high', 'medium']
                    ),
                    'metrics': result.get('metrics', {}),
                    'engagement': result.get('engagement', {}),
                    'ui_flags': result.get('ui_flags', {}),
                    'ui_message': result.get('ui_message', {}),
                },
                'session_metrics_count': self.session_metric_totals.get('total_frames', 0),
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

        except Exception:
            logger.exception(
                "Face validation failed",
                extra={"user_id": self.user_id, "session_id": self.session_id},
            )
            await self.send_error()
        finally:
            if processing_started:
                self.inference_running = False

    def _message_too_large(self, text_data):
        if text_data is None:
            return False
        return len(text_data.encode('utf-8')) > self.MAX_TEXT_MESSAGE_BYTES

    async def _allow_message(self):
        return self.rate_limiter.allow()

    def _now(self):
        return time.monotonic()

    def _should_process_frame(self, now=None):
        if self.inference_running:
            return False

        if now is None:
            now = self._now()
        if self.last_processed_frame_at is None:
            return True

        return (
            now - self.last_processed_frame_at
            >= self.FRAME_PROCESSING_INTERVAL_SECONDS
        )

    def _decoded_frame_too_large(self, frame_bgr):
        frame_height, frame_width = frame_bgr.shape[:2]
        frame_pixels = frame_width * frame_height
        return (
            frame_width > self.MAX_DECODED_FRAME_WIDTH
            or frame_height > self.MAX_DECODED_FRAME_HEIGHT
            or frame_pixels > self.MAX_DECODED_FRAME_PIXELS
        )

    def _assess_frame_quality(self, frame_bgr):
        if not isinstance(frame_bgr, np.ndarray):
            return {
                'blurry': False,
                'low_light': False,
                'blur_score': 0.0,
                'brightness_score': 0.0,
                'contrast_score': 0.0,
            }

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness_score = float(np.mean(gray))
        contrast_score = float(np.std(gray))
        low_light = (
            brightness_score < self.LOW_LIGHT_BRIGHTNESS_THRESHOLD
            or contrast_score < self.LOW_LIGHT_CONTRAST_THRESHOLD
        )

        return {
            'blurry': blur_score < self.BLUR_VARIANCE_THRESHOLD,
            'low_light': low_light,
            'blur_score': round(blur_score, 2),
            'brightness_score': round(brightness_score, 2),
            'contrast_score': round(contrast_score, 2),
        }

    def _record_frame_quality(self, quality):
        if quality.get('blurry') or quality.get('low_light'):
            self.bad_quality_frame_count += 1
        else:
            self.bad_quality_frame_count = 0

        return self.bad_quality_frame_count >= self.BAD_QUALITY_WARNING_FRAME_THRESHOLD

    def _apply_frame_quality(self, result, quality):
        analysis = result.setdefault('analysis', {})
        metrics = result.setdefault('metrics', {})

        analysis['blurry'] = bool(quality.get('blurry', False))
        low_light = bool(analysis.get('low_light', False)) or bool(quality.get('low_light', False))
        analysis['low_light'] = low_light
        quality['low_light'] = low_light
        metrics['blur_score'] = quality.get('blur_score', 0.0)
        metrics['brightness_score'] = quality.get('brightness_score', 0.0)
        metrics['contrast_score'] = quality.get('contrast_score', 0.0)

        poor_quality = analysis['blurry'] or analysis['low_light']
        warning_triggered = bool(quality.get('warning_triggered', False))
        analysis['confidence'] = 0.5 if poor_quality else 1.0
        result['quality'] = quality

        if not warning_triggered:
            return

        result['concentration_score'] = min(result.get('concentration_score', 0), 3)
        result['concentration_level'] = 'low'
        result['message'] = 'Poor frame quality'
        engagement = result.setdefault('engagement', {})
        engagement['video_attentive'] = False
        engagement['trigger_feedback'] = True

    def _apply_temporal_smoothing(self, result):
        analysis = result.setdefault('analysis', {})
        quality = result.setdefault('quality', {})
        engagement = result.setdefault('engagement', {})
        metrics = result.setdefault('metrics', {})

        confidence = float(analysis.get('confidence', 1.0))
        gaze_ratio = metrics.get('gaze_ratio')
        try:
            gaze_ratio = float(gaze_ratio)
        except (TypeError, ValueError):
            gaze_ratio = None
        gaze_reliable = (
            gaze_ratio is not None
            and self.GAZE_RATIO_MIN_RELIABLE <= gaze_ratio <= self.GAZE_RATIO_MAX_RELIABLE
        )
        analysis['gaze_reliable'] = gaze_reliable
        analysis['gaze_confidence'] = 0.8 if gaze_reliable else 0.3

        eyes_open = not bool(analysis.get('eyes_closed', False))
        head_pose_valid = bool(
            analysis.get(
                'head_pose_valid',
                analysis.get('head_pose_ok', True),
            )
        )
        frame_state = {
            'face_detected': bool(result.get('face_detected', False)),
            'eyes_open': eyes_open,
            'gaze_in_range': bool(analysis.get('gaze_in_range', True)),
            'gaze_state': analysis.get('gaze_state') or metrics.get('gaze_state') or 'CENTER',
            'gaze_reliable': gaze_reliable,
            'head_pose_valid': head_pose_valid,
            'blurry': bool(quality.get('blurry', False)),
            'low_light': bool(quality.get('low_light', False)),
            'confidence': confidence,
        }
        clear_side_gaze = frame_state['gaze_state'] in ['LEFT', 'RIGHT']
        gaze_is_bad = (
            frame_state['gaze_reliable']
            and clear_side_gaze
            and not frame_state['gaze_in_range']
        )
        analysis['clear_side_gaze'] = clear_side_gaze
        frame_state['bad'] = (
            not frame_state['face_detected']
            or not frame_state['eyes_open']
            or gaze_is_bad
            or not frame_state['head_pose_valid']
            or frame_state['blurry']
            or frame_state['low_light']
            or frame_state['confidence'] < 0.6
        )

        self.temporal_window.append(frame_state)
        bad_frame_count = sum(1 for frame in self.temporal_window if frame['bad'])
        smoothed_confidence = round(
            sum(frame['confidence'] for frame in self.temporal_window)
            / len(self.temporal_window),
            2,
        )
        warning_triggered = bad_frame_count >= self.TEMPORAL_BAD_FRAME_THRESHOLD

        result['temporal'] = {
            'bad_frame_count': bad_frame_count,
            'window_size': len(self.temporal_window),
            'smoothed_confidence': smoothed_confidence,
            'warning_triggered': warning_triggered,
        }
        analysis['eyes_open'] = eyes_open
        analysis['head_pose_valid'] = head_pose_valid

        if warning_triggered:
            result['concentration_score'] = min(result.get('concentration_score', 0), 3)
            result['concentration_level'] = 'low'
            result['message'] = 'Repeated poor attention signals'
            engagement['video_attentive'] = False
            engagement['trigger_feedback'] = True
            self._normalize_engagement_state(engagement)
            return

        engagement['trigger_feedback'] = False
        if frame_state['bad'] and result.get('concentration_level') == 'low':
            result['concentration_score'] = max(result.get('concentration_score', 0), 4)
            result['concentration_level'] = 'medium'
            result['message'] = 'Transient frame variation'
        elif not frame_state['bad'] and result.get('concentration_level') == 'low':
            result['concentration_score'] = max(result.get('concentration_score', 0), 4)
            result['concentration_level'] = 'medium'
            result['message'] = 'Borderline attention signal'
        elif (
            not frame_state['bad']
            and not frame_state['gaze_reliable']
            and not frame_state['gaze_in_range']
            and result.get('concentration_level') == 'low'
        ):
            result['concentration_score'] = max(result.get('concentration_score', 0), 4)
            result['concentration_level'] = 'medium'
            result['message'] = 'Unreliable gaze signal'

        self._normalize_engagement_state(engagement)

    def _normalize_engagement_state(self, engagement):
        if engagement.get('state') == 'watching_video':
            engagement['video_attentive'] = True
        elif engagement.get('video_attentive') is False and engagement.get('state') == 'watching_video':
            engagement['state'] = 'idle_distracted'

    def _apply_ui_alert_stability(self, result):
        """Suppress one-frame popup candidates without changing response schema."""
        ui_flags = result.get('ui_flags')
        ui_message = result.get('ui_message')
        if not isinstance(ui_flags, dict) or not isinstance(ui_message, dict):
            return

        reason = str(ui_message.get('reason') or '').strip().lower()
        severity = str(ui_message.get('severity') or '').strip().lower()
        if severity != 'warning' or not reason or reason == 'focused':
            self.ui_warning_reason = None
            self.ui_warning_count = 0
            return

        if reason == self.ui_warning_reason:
            self.ui_warning_count += 1
        else:
            self.ui_warning_reason = reason
            self.ui_warning_count = 1

        if self.ui_warning_count < self._ui_alert_threshold_for_reason(reason):
            ui_flags['should_show_alert'] = False

    def _ui_alert_threshold_for_reason(self, reason):
        critical_reasons = {
            'face_missing',
            'eyes_closed',
            'yawning',
            'drowsy',
            'low_light',
        }
        if reason in critical_reasons:
            return 1
        return self.UI_ALERT_NOISY_REASON_THRESHOLD

    def _new_metric_totals(self):
        return {
            'total_frames': 0,
            'sampled_frames': 0,
            'concentration_score_sum': 0.0,
            'confidence_sum': 0.0,
            'confidence_count': 0,
            'gaze_ratio_sum': 0.0,
            'max_inattention_duration': 0.0,
            'bad_frame_count': 0,
            'face_detected_count': 0,
            'video_attentive_count': 0,
            'head_pose_ok_count': 0,
            'eyes_closed_count': 0,
            'yawning_count': 0,
            'drowsy_count': 0,
            'side_gaze_count': 0,
            'gaze_warning_count': 0,
            'blurry_count': 0,
            'low_light_count': 0,
        }

    def _record_session_metric(self, metric):
        self.session_metrics.append(metric)
        totals = self.session_metric_totals
        totals['total_frames'] += 1
        totals['sampled_frames'] += 1
        totals['concentration_score_sum'] += metric.get('concentration_score', 0)
        confidence = metric.get('confidence')
        if confidence is not None:
            totals['confidence_sum'] += float(confidence or 0.0)
            totals['confidence_count'] += 1
        totals['gaze_ratio_sum'] += metric.get('gaze_ratio', 0.0)
        totals['max_inattention_duration'] = max(
            totals['max_inattention_duration'],
            metric.get('inattention_duration', 0.0),
        )
        totals['face_detected_count'] += int(bool(metric.get('face_detected')))
        totals['video_attentive_count'] += int(bool(metric.get('video_attentive')))
        totals['head_pose_ok_count'] += int(bool(metric.get('head_pose_ok')))
        totals['eyes_closed_count'] += int(bool(metric.get('eyes_closed')))
        totals['bad_frame_count'] += int(bool(metric.get('bad_frame')))
        totals['yawning_count'] += int(bool(metric.get('yawning')))
        totals['drowsy_count'] += int(metric.get('drowsy_state', 0.2) != 0.2)
        totals['side_gaze_count'] += int(metric.get('gaze_state') in ['LEFT', 'RIGHT'])
        totals['gaze_warning_count'] += int(metric.get('gaze_state') in ['LEFT', 'RIGHT'])
        totals['blurry_count'] += int(bool(metric.get('blurry')))
        totals['low_light_count'] += int(bool(metric.get('low_light')))

    async def handle_update_settings(self, data):
        try:
            settings = data.get('settings', {})
            self.validation_settings.update(settings)
            await self.send(text_data=json.dumps({
                'type': 'settings_updated',
                'settings': self.validation_settings,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception:
            logger.exception(
                "Settings update failed",
                extra={"user_id": self.user_id, "session_id": self.session_id},
            )
            await self.send_error()

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
        except Exception:
            logger.exception(
                "Guidelines retrieval failed",
                extra={"user_id": self.user_id, "session_id": self.session_id},
            )
            await self.send_error()

    def _build_session_summary(self, metrics):
        aggregate_total = self.session_metric_totals.get('total_frames', 0)
        if aggregate_total:
            totals = self.session_metric_totals

            def aggregate_pct(key):
                return round((totals[key] / aggregate_total) * 100, 2)

            avg_concentration = totals['concentration_score_sum'] / aggregate_total
            avg_gaze_ratio = totals['gaze_ratio_sum'] / aggregate_total
            return {
                'total_frames': aggregate_total,
                'stored_metric_samples': len(self.session_metrics),
                'avg_concentration_score': round(avg_concentration, 2),
                'final_attention_score_percent': round((avg_concentration / 8.0) * 100, 2),
                'avg_gaze_ratio': round(avg_gaze_ratio, 4),
                'max_inattention_duration': round(totals['max_inattention_duration'], 2),
                'face_detection_rate': aggregate_pct('face_detected_count'),
                'attention_engagement_rate': aggregate_pct('video_attentive_count'),
                'head_stability_rate': aggregate_pct('head_pose_ok_count'),
                'eye_closed_rate': aggregate_pct('eyes_closed_count'),
                'yawning_rate': aggregate_pct('yawning_count'),
                'drowsy_rate': aggregate_pct('drowsy_count'),
                'side_gaze_rate': aggregate_pct('side_gaze_count'),
                'low_light_rate': aggregate_pct('low_light_count'),
                'eyes_closed_frames': totals['eyes_closed_count'],
                'yawning_frames': totals['yawning_count'],
                'side_gaze_frames': totals['side_gaze_count'],
                'low_light_frames': totals['low_light_count'],
            }

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
                    'metrics_collected': self.session_metric_totals.get('total_frames', 0),
                    'stored_metric_samples': len(self.session_metrics),
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
        except Exception:
            logger.exception(
                "Stats retrieval failed",
                extra={"user_id": self.user_id, "session_id": self.session_id},
            )
            await self.send_error()

    async def send_error(self, error_code=None, message=None):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error_code': error_code or self.SAFE_ERROR_CODE,
            'message': message or self.SAFE_ERROR_MESSAGE,
        }))

    async def send_frame_too_large_error(self):
        await self.send_error(
            self.FRAME_TOO_LARGE_ERROR_CODE,
            self.FRAME_TOO_LARGE_ERROR_MESSAGE,
        )

    async def send_frame_skipped(self, frame_id=None):
        response_data = {
            'type': 'validation_result',
            'frame_id': frame_id,
            'result': {
                'frame_id': frame_id,
                'frame_sampled': False,
                'message': 'Frame skipped',
            },
            'session_metrics_count': self.session_metric_totals.get('total_frames', 0),
            'user_id': self.user_id,
            'timestamp': datetime.now().isoformat(),
        }
        await self.send(text_data=json.dumps(response_data))

    # 🔥 NO TOP-LEVEL MODEL IMPORTS - LAZY LOADING ONLY
    @database_sync_to_async
    def _create_sessions_sync(self, user_id, session_id, metrics):
        """Persist one aggregate attention row per session."""
        from django.db import transaction
        from apps.progresstracker.models import FaceAttentionSession  # UPDATE THIS PATH
        summary = self._build_session_summary(metrics)
        attention_engagement_rate = summary.get('attention_engagement_rate', 0.0)
        aggregate = self._build_session_aggregate()
        latest_metric = metrics[-1] if metrics else {}
        defaults = {
            'concentration_score': aggregate['average_concentration_score'],
            'gaze_ratio_avg': summary.get('avg_gaze_ratio', 0.0),
            'inattention_duration': summary.get('max_inattention_duration', 0.0),
            'drowsy_state': latest_metric.get('drowsy_state', 0.2),
            'face_detected': summary.get('face_detection_rate', 0.0) > 0.0,
            'video_attentive': summary.get('attention_engagement_rate', 0.0) > 0.0,
            'eyes_closed': aggregate['eyes_closed_count'] > 0,
            'yawning': summary.get('yawning_frames', 0) > 0,
            'gaze_state': latest_metric.get('gaze_state') or '',
            'head_pose_ok': summary.get('head_stability_rate', 0.0) > 0.0,
            'low_light': aggregate['low_light_frame_count'] > 0,
            'brightness_score': latest_metric.get('brightness_score', 0.0),
            'pitch': latest_metric.get('pitch', 0.0),
            'yaw': latest_metric.get('yaw', 0.0),
            'roll': latest_metric.get('roll', 0.0),
            'blink_ratio': latest_metric.get('blink_ratio', 0.0),
            'yawn_distance': latest_metric.get('yawn_distance', 0.0),
            'attention_engagement_rate': attention_engagement_rate,
            **aggregate,
        }

        with transaction.atomic():
            FaceAttentionSession.objects.update_or_create(
                user_id=user_id,
                session_id=session_id,
                defaults=defaults,
            )

    def _build_session_aggregate(self):
        totals = self.session_metric_totals
        total_frames = totals.get('total_frames', 0)
        confidence_count = totals.get('confidence_count', 0)
        avg_confidence = (
            totals.get('confidence_sum', 0.0) / confidence_count
            if confidence_count else
            0.0
        )
        avg_concentration = (
            totals.get('concentration_score_sum', 0.0) / total_frames
            if total_frames else
            0.0
        )
        if self.session_started_monotonic is not None:
            session_duration_seconds = time.monotonic() - self.session_started_monotonic
        elif self.session_started_at is not None:
            session_duration_seconds = time.time() - self.session_started_at
        else:
            session_duration_seconds = 0.0

        return {
            'total_processed_frames': int(total_frames),
            'sampled_frames': int(totals.get('sampled_frames', total_frames)),
            'average_confidence': round(avg_confidence, 4),
            'average_concentration_score': round(avg_concentration, 2),
            'bad_frame_count': int(totals.get('bad_frame_count', 0)),
            'blurry_frame_count': int(totals.get('blurry_count', 0)),
            'low_light_frame_count': int(totals.get('low_light_count', 0)),
            'eyes_closed_count': int(totals.get('eyes_closed_count', 0)),
            'gaze_warning_count': int(totals.get('gaze_warning_count', 0)),
            'session_duration_seconds': round(max(session_duration_seconds, 0.0), 2),
        }

    @database_sync_to_async
    def _update_user_score_sync(self, user_id, final_score):
        """CHANGE 'apps.yourapp.models' to your actual app path"""
        from apps.users.models import Users  # UPDATE THIS PATH
        user = Users.objects.get(id=user_id)
        user.ai_assessment_score = final_score
        user.save(update_fields=['ai_assessment_score'])
        return user.ai_assessment_score

    async def _save_assessment_score(self):
        total_frames = self.session_metric_totals.get('total_frames', 0)
        if self.assessment_score_saved or not self.user_id or not total_frames:
            return

        avg_concentration = self.session_metric_totals['concentration_score_sum'] / total_frames
        final_score = round((avg_concentration / 8.0) * 100, 2)

        await self._create_sessions_sync(self.user_id, self.session_id, list(self.session_metrics))
        await self._update_user_score_sync(self.user_id, final_score)
        self.assessment_score_saved = True
