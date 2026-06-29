import cv2
import dlib
import numpy as np
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Tuple
import os
import time
from math import hypot
from imutils import face_utils

import logging

logger = logging.getLogger(__name__)
SAFE_ANALYSIS_ERROR_MESSAGE = "Unable to process frame safely"

# --------------------------
# PATHS & MODEL LOADING
# --------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
FILES_DIR = os.path.join(PROJECT_ROOT, "files")

logger.info(f"SCRIPT_DIR: {SCRIPT_DIR}")
logger.info(f"PROJECT_ROOT: {PROJECT_ROOT}")
logger.info(f"FILES_DIR: {FILES_DIR}")
logger.info(
    f"PREDICTOR exists: "
    f"{os.path.exists(os.path.join(FILES_DIR, 'shape_predictor_68_face_landmarks.dat'))}"
)

DETECTION_MODEL_PATH = os.path.join(FILES_DIR, "haarcascade_frontalface_default.xml")
PREDICTOR_PATH = os.path.join(FILES_DIR, "shape_predictor_68_face_landmarks.dat")

face_detection = cv2.CascadeClassifier(DETECTION_MODEL_PATH)
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(PREDICTOR_PATH)

# --------------------------
# CONSTANTS / STATE
# --------------------------
GAZE_LOW = 0.6
GAZE_HIGH = 3.5
HEAD_LIMIT = 25
EXPECTED_FPS = 30
LOW_LIGHT_THRESHOLD = 80.0
INATTENTION_LIMIT = 4.0
READING_WINDOW = 10.0
READING_MIN_AMP = 0.3
READING_MIN_FREQ = 0.1
READING_MAX_FREQ = 1.5
YAWN_THRESH = 15.0
BLINK_RATIO_THRESHOLD = 4.75
EYE_OPEN_PROBABILITY_THRESHOLD = 0.3

# State variables are now passed via WebSocket consumer face_data

# Camera intrinsics
K = [6.5308391993466671e+002, 0.0, 3.1950000000000000e+002,
     0.0, 6.5308391993466671e+002, 2.3950000000000000e+002,
     0.0, 0.0, 1.0]
D = [7.0834633684407095e-002, 6.9140193737175351e-002, 0.0, 0.0, -1.3073460323689292e+000]
cam_matrix = np.array(K).reshape(3, 3).astype(np.float32)
dist_coeffs = np.array(D).reshape(5, 1).astype(np.float32)

object_pts = np.float32([
    [6.825897, 6.760612, 4.402142],
    [1.330353, 7.122144, 6.903745],
    [-1.330353, 7.122144, 6.903745],
    [-6.825897, 6.760612, 4.402142],
    [5.311432, 5.485328, 3.987654],
    [1.789930, 5.393625, 4.413414],
    [-1.789930, 5.393625, 4.413414],
    [-5.311432, 5.485328, 3.987654],
    [2.005628, 1.409845, 6.165652],
    [-2.005628, 1.409845, 6.165652],
    [2.774015, -2.080775, 5.048531],
    [-2.774015, -2.080775, 5.048531],
    [0.000000, -3.116408, 6.097667],
    [0.000000, -7.415691, 4.070434]
])

@dataclass
class AnalysisFlags:
    face_size_adequate: bool = False
    face_centered: bool = False
    face_distance_good: bool = False
    face_not_on_edge: bool = False
    gaze_in_range: bool = False
    head_pose_ok: bool = False
    not_drowsy: bool = False
    face_present: bool = False
    reading_pattern: bool = False

def build_analysis(
    flags: AnalysisFlags,
    low_light: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    analysis = asdict(flags)
    analysis["low_light"] = bool(low_light)
    if extra:
        analysis.update(extra)
    return analysis

def build_ui_feedback(
    *,
    face_detected: bool,
    concentration_score: int = 0,
    analysis: Optional[Dict[str, Any]] = None,
    engagement: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    analysis = analysis or {}
    engagement = engagement or {}
    metrics = metrics or {}

    left_eye_prob = metrics.get("left_eye_open_probability")
    right_eye_prob = metrics.get("right_eye_open_probability")
    left_eye_closed = (
        left_eye_prob is not None
        and left_eye_prob < EYE_OPEN_PROBABILITY_THRESHOLD
    )
    right_eye_closed = (
        right_eye_prob is not None
        and right_eye_prob < EYE_OPEN_PROBABILITY_THRESHOLD
    )

    gaze_state = analysis.get("gaze_state") or metrics.get("gaze_state") or "CENTER"
    video_attentive = bool(engagement.get("video_attentive", False))
    engagement_state = engagement.get("state", "")

    flags = {
        "can_continue": False,
        "should_show_alert": True,
        "low_light": bool(analysis.get("low_light", False)),
        "face_missing": not face_detected,
        "face_not_centered": analysis.get("face_centered") is False,
        "face_too_close": bool(metrics.get("size_ratio", 0.0) > 0.6),
        "face_too_far": bool(
            metrics.get("size_ratio") is not None
            and metrics.get("size_ratio", 0.0) < 0.15
        ),
        "face_on_edge": analysis.get("face_not_on_edge") is False,
        "eyes_closed": bool(analysis.get("eyes_closed", False)),
        "left_eye_closed": bool(left_eye_closed),
        "right_eye_closed": bool(right_eye_closed),
        "yawning": bool(analysis.get("yawning", False)),
        "drowsy": analysis.get("not_drowsy") is False,
        "looking_left": gaze_state == "LEFT",
        "looking_right": gaze_state == "RIGHT",
        "looking_center": gaze_state == "CENTER",
        "head_moved": analysis.get("head_pose_ok") is False,
        "not_video_attentive": not video_attentive,
        "low_concentration": concentration_score < 7,
    }

    can_continue = (
        face_detected
        and video_attentive
        and not flags["low_light"]
        and not flags["eyes_closed"]
        and not flags["left_eye_closed"]
        and not flags["right_eye_closed"]
        and not flags["yawning"]
        and not flags["drowsy"]
        and not flags["head_moved"]
        and concentration_score >= 7
        and engagement_state == "watching_video"
    )
    flags["can_continue"] = can_continue
    flags["should_show_alert"] = not can_continue

    reason = "focused"
    title = "Focused"
    message = "You are focused. Continue watching."
    severity = "success"

    if flags["low_light"]:
        reason, title, message = (
            "low_light",
            "Lighting Alert",
            "Lighting is too low. Move to a brighter area or turn on a light.",
        )
    elif flags["face_missing"]:
        reason, title, message = (
            "face_missing",
            "Face Alert",
            "Face not detected. Please keep your face inside the camera frame.",
        )
    elif flags["left_eye_closed"] and not flags["right_eye_closed"]:
        reason, title, message = (
            "left_eye_closed",
            "Eye Alert",
            "Left eye appears closed. Please keep both eyes open.",
        )
    elif flags["right_eye_closed"] and not flags["left_eye_closed"]:
        reason, title, message = (
            "right_eye_closed",
            "Eye Alert",
            "Right eye appears closed. Please keep both eyes open.",
        )
    elif flags["eyes_closed"]:
        reason, title, message = (
            "eyes_closed",
            "Eye Alert",
            "Eyes closed detected. Please keep your eyes open and focus on the video.",
        )
    elif flags["yawning"]:
        reason, title, message = (
            "yawning",
            "Drowsiness Alert",
            "Yawning detected. Please take a short break and refocus.",
        )
    elif flags["head_moved"]:
        reason, title, message = (
            "head_moved",
            "Position Alert",
            "Head movement detected. Please keep your head facing the screen.",
        )
    elif flags["looking_left"]:
        reason, title, message = (
            "looking_left",
            "Attention Alert",
            "You are looking left. Please focus on the video.",
        )
    elif flags["looking_right"]:
        reason, title, message = (
            "looking_right",
            "Attention Alert",
            "You are looking right. Please focus on the video.",
        )
    elif flags["face_not_centered"]:
        reason, title, message = (
            "face_not_centered",
            "Position Alert",
            "Please center your face in the camera frame.",
        )
    elif flags["face_too_close"] or flags["face_too_far"]:
        reason, title, message = (
            "face_distance",
            "Position Alert",
            "Please adjust your distance from the camera.",
        )
    elif flags["face_on_edge"]:
        reason, title, message = (
            "face_on_edge",
            "Position Alert",
            "Please keep your full face visible inside the frame.",
        )
    elif flags["drowsy"]:
        reason, title, message = (
            "drowsy",
            "Drowsiness Alert",
            "Drowsiness detected. Please take a short break and refocus.",
        )
    elif flags["not_video_attentive"]:
        reason, title, message = (
            "not_video_attentive",
            "Attention Alert",
            "You seem distracted. Please focus on the video.",
        )
    elif flags["low_concentration"]:
        reason, title, message = (
            "low_concentration",
            "Attention Alert",
            "Low concentration detected. Take a moment to refocus.",
        )

    if reason != "focused":
        severity = "warning"

    return {
        "ui_flags": flags,
        "ui_message": {
            "reason": reason,
            "title": title,
            "message": message,
            "severity": severity,
        },
    }

# --------------------------
# Low-level helpers
# --------------------------
def midpoint(p1, p2) -> Tuple[int, int]:
    """Calculate midpoint between two dlib points"""
    return int((p1.x + p2.x) / 2), int((p1.y + p2.y) / 2)

def lip_distance(shape_np: np.ndarray) -> float:
    """Calculate vertical distance between lips for yawn detection"""
    top_lip = shape_np[50:53]
    top_lip = np.concatenate((top_lip, shape_np[61:64]))
    low_lip = shape_np[56:59]
    low_lip = np.concatenate((low_lip, shape_np[65:68]))
    top_mean = np.mean(top_lip, axis=0)
    low_mean = np.mean(low_lip, axis=0)
    return abs(top_mean[1] - low_mean[1])

def get_blinking_ratio(eye_points, landmarks: dlib.full_object_detection) -> float:
    """Calculate eye aspect ratio for blink detection"""
    left_point = (landmarks.part(eye_points[0]).x, landmarks.part(eye_points[0]).y)
    right_point = (landmarks.part(eye_points[3]).x, landmarks.part(eye_points[3]).y)
    center_top = midpoint(landmarks.part(eye_points[1]), landmarks.part(eye_points[2]))
    center_bottom = midpoint(landmarks.part(eye_points[5]), landmarks.part(eye_points[4]))
    
    hor_line_length = hypot(left_point[0] - right_point[0], left_point[1] - right_point[1])
    ver_line_length = hypot(center_top[0] - center_bottom[0], center_top[1] - center_bottom[1])
    
    if ver_line_length == 0:
        return 0.0
    return hor_line_length / ver_line_length

def get_gaze_ratio(frame, gray, eye_points, landmarks) -> float:
    """Calculate gaze direction ratio (left vs right in eye region)"""
    region = np.array([
        (landmarks.part(eye_points[0]).x, landmarks.part(eye_points[0]).y),
        (landmarks.part(eye_points[1]).x, landmarks.part(eye_points[1]).y),
        (landmarks.part(eye_points[2]).x, landmarks.part(eye_points[2]).y),
        (landmarks.part(eye_points[3]).x, landmarks.part(eye_points[3]).y),
        (landmarks.part(eye_points[4]).x, landmarks.part(eye_points[4]).y),
        (landmarks.part(eye_points[5]).x, landmarks.part(eye_points[5]).y),
    ], np.int32)
    
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [region], 255)
    eye = cv2.bitwise_and(gray, gray, mask=mask)
    
    min_x = np.min(region[:, 0])
    max_x = np.max(region[:, 0])
    min_y = np.min(region[:, 1])
    max_y = np.max(region[:, 1])
    
    gray_eye = eye[min_y:max_y, min_x:max_x]
    if gray_eye.size == 0:
        return 1.0
    
    _, threshold_eye = cv2.threshold(gray_eye, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    h_t, w_t = threshold_eye.shape
    
    left_side = threshold_eye[:, 0:int(w_t / 2)]
    right_side = threshold_eye[:, int(w_t / 2):]
    
    left_white = cv2.countNonZero(left_side)
    right_white = cv2.countNonZero(right_side)
    
    if left_white == 0 and right_white == 0:
        return 1.0
    if right_white == 0:
        return 5.0
    
    return left_white / float(right_white)


def get_head_pose(shape_np: np.ndarray) -> Tuple[float, float, float]:
    """Calculate head pose (pitch, yaw, roll) using PnP"""
    image_pts = np.float32([
        shape_np[17], shape_np[21], shape_np[22], shape_np[26],
        shape_np[36], shape_np[39], shape_np[42], shape_np[45],
        shape_np[31], shape_np[35], shape_np[48], shape_np[54],
        shape_np[57], shape_np[8]
    ])
    
    _, rotation_vec, translation_vec = cv2.solvePnP(object_pts, image_pts, cam_matrix, dist_coeffs)
    rotation_mat, _ = cv2.Rodrigues(rotation_vec)
    pose_mat = cv2.hconcat((rotation_mat, translation_vec))
    _, _, _, _, _, _, euler_angle = cv2.decomposeProjectionMatrix(pose_mat)
    
    pitch = float(euler_angle[0, 0])
    yaw = float(euler_angle[1, 0])
    roll = float(euler_angle[2, 0])
    
    return pitch, yaw, roll

def compute_gaze_dynamics(window: float, gaze_history: deque) -> Dict[str, float]:
    """Compute gaze frequency and amplitude from history"""
    if len(gaze_history) < 3:
        return {"freq": 0.0, "amp": 0.0}
    
    times = [t for t, _ in gaze_history]
    vals = [g for _, g in gaze_history]
    duration = times[-1] - times[0]
    
    if duration <= 0:
        return {"freq": 0.0, "amp": 0.0}
    
    amp = max(vals) - min(vals)
    
    direction_changes = 0
    last_sign = 0
    for i in range(1, len(vals)):
        diff = vals[i] - vals[i - 1]
        if abs(diff) < 1e-3:
            continue
        sign = 1 if diff > 0 else -1
        if last_sign != 0 and sign != last_sign:
            direction_changes += 1
        last_sign = sign
    
    freq = (direction_changes / 2.0) / duration
    return {"freq": freq, "amp": amp}

def update_engagement(
    gaze_ratio,
    drowsy_state,
    pitch,
    yaw,
    faces_count,
    settings,
    gaze_history,
    inattention_start,
    frame_time_seconds=None,
):
    """Update engagement state based on gaze, head pose, and drowsiness"""

    now = frame_time_seconds if frame_time_seconds is not None else time.time()
    gaze_history.append((now, gaze_ratio))
    
    while gaze_history and (now - gaze_history[0][0] > settings["reading_window"]):
        gaze_history.popleft()
    
    dyn = compute_gaze_dynamics(settings["reading_window"], gaze_history)
    freq, amp = dyn["freq"], dyn["amp"]
    
    # Video watching: gaze in range, alert, head still, face visible
    video_att = (
        settings["gaze_low"] < gaze_ratio < settings["gaze_high"]
        and drowsy_state == 0.2
        and -settings["head_limit"] <= pitch <= settings["head_limit"]
        and -settings["head_limit"] <= yaw <= settings["head_limit"]
        and faces_count >= 1
    )
    
    # Reading: similar but with gaze dynamics
    reading = (
        faces_count == 1
        and -settings["head_limit"] <= pitch <= settings["head_limit"]
        and -settings["head_limit"] <= yaw <= settings["head_limit"]
        and drowsy_state == 0.2
        and settings["gaze_low"] < gaze_ratio < settings["gaze_high"]
        and amp >= settings["reading_min_amp"]
        and settings["reading_min_freq"] <= freq <= settings["reading_max_freq"]
    )
    
    engaged = video_att or reading
    
    if not engaged:
        if inattention_start is None:
            inattention_start = now
        duration = now - inattention_start
    else:
        duration = 0.0
        inattention_start = None
    
    trigger = (not engaged) and (duration >= settings["inattention_limit"])
    
    if reading:
        state = "reading_pdf"
    elif video_att:
        state = "watching_video"
    else:
        state = "idle_distracted"
    
    return {
        "state": state,
        "trigger_feedback": trigger,
        "inattention_duration": duration,
        "gaze_freq": freq,
        "gaze_amp": amp,
        "video_attentive": video_att,
        "reading_focus": reading,
        "new_inattention_start": inattention_start,
    }

# --------------------------
# MAIN ANALYSIS FUNCTION (USES CLIENT-PROVIDED FRAME)
# --------------------------
def analyze_face_attention_with_models(face_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze face attention from client-provided frame.
    
    face_data from WebSocket:
    {
        'x': int,                  # Face X coordinate from client
        'y': int,                  # Face Y coordinate from client
        'width': int,              # Face width from client
        'height': int,             # Face height from client
        'frame_width': int,        # Frame width (640)
        'frame_height': int,       # Frame height (480)
        'frame_bgr': np.ndarray,   # ✅ ACTUAL OPENCV FRAME (required)
        'custom_settings': {...}   # Optional custom tolerances
    }
    
    Returns: Dict with all analysis results including:
    - face_detected: bool
    - concentration_level: str (high/medium/low/error)
    - concentration_score: int (0-8)
    - metrics: Dict with gaze_ratio, pitch, yaw, blink_ratio, yawn_distance, etc.
    - engagement: Dict with state, inattention_duration, gaze_freq, etc.
    - recommendations: List of actionable feedback
    """
    try:
        # Extract client-provided data
        client_x = face_data.get("x", 0)
        client_y = face_data.get("y", 0)
        client_w = face_data.get("width", 0)
        client_h = face_data.get("height", 0)
        frame_width = face_data.get("frame_width", 640)
        frame_height = face_data.get("frame_height", 480)
        custom_settings = face_data.get("custom_settings", {}) or {}
        mode = face_data.get("mode", "video")
        pdf_is_visible = bool(face_data.get("pdf_is_visible", False))
        is_assessment = bool(face_data.get("is_assessment", False))
        eye_data = face_data.get("eye", {}) or {}
        last_attention_state = face_data.get("last_attention_state", "idle_distracted")
        expected_fps = float(face_data.get("expected_fps", EXPECTED_FPS) or EXPECTED_FPS)
        frame_time_seconds = face_data.get("frame_time_seconds")
        if frame_time_seconds is None:
            frame_time_seconds = time.time()
        else:
            frame_time_seconds = float(frame_time_seconds)
        
        # Extract state passed from consumer
        gaze_history = face_data.get("gaze_history") if face_data.get("gaze_history") is not None else deque()
        blink_history = face_data.get("blink_history") if face_data.get("blink_history") is not None else deque()
        score_history = face_data.get("score_history") if face_data.get("score_history") is not None else deque(maxlen=5)
        inattention_start = face_data.get("inattention_start")

        settings = {
            "gaze_low": custom_settings.get("gaze_low", GAZE_LOW),
            "gaze_high": custom_settings.get("gaze_high", GAZE_HIGH),
            "head_limit": custom_settings.get("head_limit", HEAD_LIMIT),
            "inattention_limit": custom_settings.get("inattention_limit", INATTENTION_LIMIT),
            "reading_window": custom_settings.get("reading_window", READING_WINDOW),
            "reading_min_amp": custom_settings.get("reading_min_amp", READING_MIN_AMP),
            "reading_max_freq": custom_settings.get("reading_max_freq", READING_MAX_FREQ),
            "reading_min_freq": custom_settings.get("reading_min_freq", READING_MIN_FREQ),
            "expected_fps": expected_fps,
        }
        
        # ✅ USE FRAME PROVIDED BY CLIENT (decoded from base64 by consumer)
        frame_bgr = face_data.get("frame_bgr")
        if frame_bgr is None:
            analysis = build_analysis(AnalysisFlags())
            ui_feedback = build_ui_feedback(
                face_detected=False,
                concentration_score=0,
                analysis=analysis,
            )
            return {
                "face_detected": False,
                "concentration_level": "error",
                "concentration_score": 0,
                "message": SAFE_ANALYSIS_ERROR_MESSAGE,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "analysis": analysis,
                "face_position": {},
                "recommendations": ["Please retry with a valid camera frame"],
                **ui_feedback,
            }
        
        # Verify frame is valid OpenCV format
        if not isinstance(frame_bgr, np.ndarray):
            analysis = build_analysis(AnalysisFlags())
            ui_feedback = build_ui_feedback(
                face_detected=False,
                concentration_score=0,
                analysis=analysis,
            )
            return {
                "face_detected": False,
                "concentration_level": "error",
                "concentration_score": 0,
                "message": SAFE_ANALYSIS_ERROR_MESSAGE,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "analysis": analysis,
                "face_position": {},
                "recommendations": ["Please retry with a valid camera frame"],
                **ui_feedback,
            }
        
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        brightness_score = float(np.mean(gray))
        low_light = brightness_score < custom_settings.get("low_light_threshold", LOW_LIGHT_THRESHOLD)
        gray = cv2.equalizeHist(gray) 

        # Require a real ML Kit face box from the same frame. Server-side
        # detectors can false-positive on background, so they should not turn
        # a no-face frame into a successful validation.
        client_box_missing = client_w <= 0 or client_h <= 0
        client_box_is_full_frame = (
            client_x <= 0
            and client_y <= 0
            and client_w >= frame_width * 0.95
            and client_h >= frame_height * 0.95
        )
        client_box_out_of_frame = (
            client_x < 0
            or client_y < 0
            or client_x + client_w > frame_width
            or client_y + client_h > frame_height
        )
        if client_box_missing or client_box_is_full_frame or client_box_out_of_frame:
            engagement_info = update_engagement(
                0.0, 0.8, 0.0, 0.0, 0, settings, gaze_history, inattention_start, frame_time_seconds
            )
            engagement_info["state"] = "idle_distracted"
            engagement_info["video_attentive"] = False
            engagement_info["reading_focus"] = False
            analysis = build_analysis(AnalysisFlags(), low_light)
            metrics = {
                "faces_count": 0,
                "brightness_score": round(brightness_score, 2),
            }
            ui_feedback = build_ui_feedback(
                face_detected=False,
                concentration_score=0,
                analysis=analysis,
                engagement=engagement_info,
                metrics=metrics,
            )
            return {
                "face_detected": False,
                "concentration_level": "low",
                "concentration_score": 0,
                "message": "No valid client face box received",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "analysis": analysis,
                "face_position": {
                    "client_x": int(client_x),
                    "client_y": int(client_y),
                    "client_width": int(client_w),
                    "client_height": int(client_h),
                    "frame_width": int(frame_width),
                    "frame_height": int(frame_height),
                },
                "engagement": engagement_info,
                "inattention_start": engagement_info.get("new_inattention_start"),
                "recommendations": [
                    "Improve room lighting for better face detection"
                    if low_light else
                    "Ensure the camera frame and ML Kit face box are from the same image"
                ],
                "metrics": metrics,
                **ui_feedback,
            }
        
        # ✅ DETECT FACES WITH HAAR CASCADE ON PROVIDED FRAME
        faces_haar = face_detection.detectMultiScale(
            gray,  # Use preprocessed gray
            scaleFactor=1.05,  # More scales for varying distances
            minNeighbors=4,    # Less strict for real-time
            minSize=(40, 40),  # Better for adult faces
            flags=cv2.CASCADE_SCALE_IMAGE
        )
                
        faces_haar = list(faces_haar)
        client_face_center = (
            client_x + (client_w / 2.0),
            client_y + (client_h / 2.0),
        )

        if faces_haar:
            # Mobile frames can contain video content plus the selfie preview.
            # Prefer the server-detected face closest to the ML Kit face box.
            faces_haar = [
                min(
                    faces_haar,
                    key=lambda face: (
                        (face[0] + face[2] / 2.0 - client_face_center[0]) ** 2
                        + (face[1] + face[3] / 2.0 - client_face_center[1]) ** 2
                    ),
                )
            ]
        else:
            # ML Kit has already supplied a valid same-frame face box. Use it
            # as the server face candidate when Haar misses mobile frames.
            faces_haar = [(int(client_x), int(client_y), int(client_w), int(client_h))]
        
        # Use first detected face
        x, y, fw, fh = faces_haar[0]
        face_center_x = x + fw // 2
        face_center_y = y + fh // 2
        frame_center_x = w // 2
        frame_center_y = h // 2

        # ✅ GEOMETRIC VALIDATION USING CLIENT COORDINATES
        flags = AnalysisFlags()
        
        # Get custom tolerances or use defaults
        center_tolerance = custom_settings.get("center", 0.25)
        size_min = custom_settings.get("size_min", 0.15)
        size_max = custom_settings.get("size_max", 0.6)
        edge_margin = custom_settings.get("edge_margin", 0.1)
        
        # Calculate client-side coordinates
        client_face_center_x = client_x + client_w // 2
        client_face_center_y = client_y + client_h // 2
        client_frame_center_x = frame_width // 2
        client_frame_center_y = frame_height // 2
        
        min_face_size = frame_width * size_min
        max_face_size = frame_width * size_max
        flags.face_size_adequate = min_face_size <= client_w <= max_face_size
        
        center_tol_x = frame_width * center_tolerance
        center_tol_y = frame_height * center_tolerance
        x_diff = abs(client_face_center_x - client_frame_center_x)
        y_diff = abs(client_face_center_y - client_frame_center_y)
        flags.face_centered = (x_diff <= center_tol_x and y_diff <= center_tol_y)
        
        face_area_ratio = (client_w * client_h) / float(frame_width * frame_height)
        flags.face_distance_good = 0.02 <= face_area_ratio <= 0.3
        
        flags.face_not_on_edge = (
            client_x > frame_width * edge_margin
            and client_y > frame_height * edge_margin
            and (client_x + client_w) < frame_width * (1 - edge_margin)
            and (client_y + client_h) < frame_height * (1 - edge_margin)
        )
        
        # ✅ DLIB FACIAL LANDMARKS ON ACTUAL FRAME
        rects = detector(gray, 0)
        if len(rects) == 0:
            # Mobile ML Kit has already validated the face box on the same
            # frame. Use it as a landmark fallback when dlib's full-frame
            # detector misses intermittent mobile frames.
            rects = [
                dlib.rectangle(
                    int(client_x),
                    int(client_y),
                    int(client_x + client_w),
                    int(client_y + client_h),
                )
            ]
        faces_count = len(rects)
        flags.face_present = faces_count > 0

        if faces_count == 0:
            engagement_info = update_engagement(
                0.0, 0.8, 0.0, 0.0, 0, settings, gaze_history, inattention_start, frame_time_seconds
            )
            engagement_info["state"] = "idle_distracted"
            engagement_info["video_attentive"] = False
            engagement_info["reading_focus"] = False
            analysis = build_analysis(AnalysisFlags(), low_light)
            metrics = {
                "faces_count": 0,
                "brightness_score": round(brightness_score, 2),
            }
            ui_feedback = build_ui_feedback(
                face_detected=False,
                concentration_score=0,
                analysis=analysis,
                engagement=engagement_info,
                metrics=metrics,
            )
            return {
                "face_detected": False,
                "concentration_level": "low",
                "concentration_score": 0,
                "message": "No clear face landmarks detected",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "analysis": analysis,
                "face_position": {
                    "server_x": int(x),
                    "server_y": int(y),
                    "server_width": int(fw),
                    "server_height": int(fh),
                    "client_x": int(client_x),
                    "client_y": int(client_y),
                    "client_width": int(client_w),
                    "client_height": int(client_h),
                    "frame_width": int(frame_width),
                    "frame_height": int(frame_height),
                },
                "engagement": engagement_info,
                "inattention_start": engagement_info.get("new_inattention_start"),
                "recommendations": [
                    "Improve room lighting for better face detection"
                    if low_light else
                    "Ensure your face is centered and the frame orientation matches the face box"
                ],
                "metrics": metrics,
                **ui_feedback,
            }
        
        # Initialize metrics
        gaze_ratio = 1.0
        blink_ratio = 0.0
        yawn_distance = 0.0
        pitch = yaw = roll = 0.0
        drowsy_state = 0.2
        
        # Extract facial features if face detected by dlib
        if faces_count > 0:
            dlib_rect = rects[0]
            landmarks = predictor(gray, dlib_rect)
            shape_np = face_utils.shape_to_np(landmarks)
            
            # Yawn detection
            yawn_distance = lip_distance(shape_np)
            
            # Blink detection
            left_eye_ratio = get_blinking_ratio([36, 37, 38, 39, 40, 41], landmarks)
            right_eye_ratio = get_blinking_ratio([42, 43, 44, 45, 46, 47], landmarks)
            blink_ratio = (left_eye_ratio + right_eye_ratio) / 2.0
            
            # Gaze tracking
            gaze_left = get_gaze_ratio(frame_bgr, gray, [36, 37, 38, 39, 40, 41], landmarks)
            gaze_right = get_gaze_ratio(frame_bgr, gray, [42, 43, 44, 45, 46, 47], landmarks)
            gaze_ratio = (gaze_left + gaze_right) / 2.0
            
            # Head pose estimation
            pitch, yaw, roll = get_head_pose(shape_np)
            
        left_eye_open_probability = eye_data.get("left_open_probability")
        right_eye_open_probability = eye_data.get("right_open_probability")
        mlkit_eyes_closed = False
        if left_eye_open_probability is not None and right_eye_open_probability is not None:
            left_eye_open_probability = float(left_eye_open_probability)
            right_eye_open_probability = float(right_eye_open_probability)
            mlkit_eyes_closed = (
                left_eye_open_probability < EYE_OPEN_PROBABILITY_THRESHOLD
                and right_eye_open_probability < EYE_OPEN_PROBABILITY_THRESHOLD
            )

        eyes_closed = bool(blink_ratio > BLINK_RATIO_THRESHOLD or mlkit_eyes_closed)
        yawning = bool(yawn_distance > YAWN_THRESH)

        # Drowsiness detection
        if yawning or eyes_closed:
            drowsy_state = 0.8
        
        # Validate gaze and head pose
        flags.gaze_in_range = settings["gaze_low"] < gaze_ratio < settings["gaze_high"]
        flags.head_pose_ok = (
            -settings["head_limit"] <= pitch <= settings["head_limit"]
            and -settings["head_limit"] <= yaw <= settings["head_limit"]
        )
        flags.not_drowsy = (drowsy_state == 0.2)

        if gaze_ratio <= settings["gaze_low"]:
            gaze_state = "RIGHT"
        elif gaze_ratio > settings["gaze_high"]:
            gaze_state = "LEFT"
        else:
            gaze_state = "CENTER"
        analysis_extra = None
        if not is_assessment:
            analysis_extra = {
                "eyes_closed": eyes_closed,
                "yawning": yawning,
                "gaze_state": gaze_state,
            }
        
        # Calculate engagement
        engagement_info = update_engagement(
            gaze_ratio,
            drowsy_state,
            pitch,
            yaw,
            faces_count,
            settings,
            gaze_history,
            inattention_start,
            frame_time_seconds,
        )
        flags.reading_pattern = engagement_info.get("reading_focus", False)
        
        # ✅ CONCENTRATION SCORE (0-8 flags)
        raw_concentration_score = sum(bool(v) for v in asdict(flags).values())
        score_history.append(raw_concentration_score)
        concentration_score = round(sum(score_history) / len(score_history))
        
        if concentration_score >= 6:
            concentration_level = "high"
            msg = "Excellent concentration detected"
        elif concentration_score >= 4:
            concentration_level = "medium"
            msg = "Good concentration level"
        else:
            concentration_level = "low"
            msg = "Poor concentration - please adjust position"

        gaze_in_video_zone = engagement_info.get("video_attentive", False)
        gaze_in_pdf_zone = engagement_info.get("reading_focus", False)

        if gaze_in_video_zone:
            can_keep_watching = (
                last_attention_state == "watching_video"
                and concentration_score >= 6
            )
            if concentration_score >= 7 or can_keep_watching:
                engagement_info["state"] = "watching_video"
                engagement_info["video_attentive"] = True
            else:
                engagement_info["state"] = "idle_distracted"
                engagement_info["video_attentive"] = False
        elif (
            mode == "video"
            and concentration_score >= 7
            and flags.face_present
            and flags.face_size_adequate
            and flags.face_centered
            and flags.face_distance_good
            and flags.face_not_on_edge
            and flags.head_pose_ok
            and flags.not_drowsy
            and not eyes_closed
            and not yawning
        ):
            engagement_info["state"] = "watching_video"
            engagement_info["video_attentive"] = True
        elif mode == "reading" and gaze_in_pdf_zone and pdf_is_visible:
            engagement_info["state"] = "reading_pdf"
            engagement_info["video_attentive"] = False
        else:
            engagement_info["state"] = "idle_distracted"
            engagement_info["video_attentive"] = False

        engagement_info["reading_focus"] = (
            mode == "reading" and gaze_in_pdf_zone and pdf_is_visible
        )
        
        # Generate recommendations
        recommendations = []
        if not flags.face_size_adequate:
            recommendations.append("Adjust your distance from the camera")
        if not flags.face_centered:
            recommendations.append("Center your face in the frame")
        if not flags.face_distance_good:
            recommendations.append("Move to optimal distance from camera")
        if not flags.face_not_on_edge:
            recommendations.append("Ensure your full face is visible within frame boundaries")
        if not flags.gaze_in_range:
            recommendations.append("Look towards the screen to improve engagement")
        if not flags.head_pose_ok:
            recommendations.append("Keep your head oriented towards the screen")
        if not flags.not_drowsy:
            recommendations.append("You appear drowsy; consider taking a short break")
        if low_light:
            recommendations.append("Improve room lighting for better face detection")
        if not recommendations:
            recommendations.append("Perfect! Maintain your current position")

        metrics = {
            "face_area_ratio": round(face_area_ratio, 4),
            "center_deviation_x": round(x_diff / float(frame_width), 4),
            "center_deviation_y": round(y_diff / float(frame_height), 4),
            "size_ratio": round(client_w / float(frame_width), 4),
            "raw_concentration_score": raw_concentration_score,
            "score_window_size": len(score_history),
            "gaze_ratio": round(gaze_ratio, 4),
            "pitch": round(pitch, 2),
            "yaw": round(yaw, 2),
            "roll": round(roll, 2),
            "blink_ratio": round(blink_ratio, 4),
            "yawn_distance": round(yawn_distance, 4),
            "drowsy_state": drowsy_state,
            "faces_count": faces_count,
            "brightness_score": round(brightness_score, 2),
            "left_eye_open_probability": left_eye_open_probability,
            "right_eye_open_probability": right_eye_open_probability,
        }
        if not is_assessment:
            metrics.update({
                "eyes_closed": eyes_closed,
                "yawning": yawning,
                "gaze_state": gaze_state,
            })

        analysis = build_analysis(flags, low_light, analysis_extra)
        ui_feedback = build_ui_feedback(
            face_detected=True,
            concentration_score=concentration_score,
            analysis=analysis,
            engagement=engagement_info,
            metrics=metrics,
        )
        
        # ✅ RETURN COMPLETE ANALYSIS
        return {
            "face_detected": True,
            "concentration_level": concentration_level,
            "concentration_score": concentration_score,
            "message": msg,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "face_position": {
                "server_x": int(x),
                "server_y": int(y),
                "server_width": int(fw),
                "server_height": int(fh),
                "client_x": int(client_x),
                "client_y": int(client_y),
                "client_width": int(client_w),
                "client_height": int(client_h),
                "frame_width": int(frame_width),
                "frame_height": int(frame_height),
            },
            "analysis": analysis,
            "engagement": engagement_info,
            "inattention_start": engagement_info.get("new_inattention_start"),
            "recommendations": recommendations,
            "metrics": metrics,
            **ui_feedback,
        }
    
    except Exception:
        logger.exception("Face attention analysis failed")
        analysis = build_analysis(AnalysisFlags())
        ui_feedback = build_ui_feedback(
            face_detected=False,
            concentration_score=0,
            analysis=analysis,
        )
        return {
            "face_detected": False,
            "concentration_level": "error",
            "concentration_score": 0,
            "message": SAFE_ANALYSIS_ERROR_MESSAGE,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "analysis": analysis,
            "face_position": {},
            "recommendations": ["Please retry with a valid camera frame"],
            **ui_feedback,
        }
