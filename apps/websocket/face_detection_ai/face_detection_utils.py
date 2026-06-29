# face_detection_utils.py
import cv2
import numpy as np
from datetime import datetime
import base64
import logging


logger = logging.getLogger(__name__)
SAFE_ANALYSIS_ERROR_MESSAGE = "Unable to process frame safely"

# Load the face detection model (Haar Cascade) - load once globally
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def analyze_face_concentration(face_data):
    """
    Analyze face concentration based on face dimensions and position
    
    Args:
        face_data: Dictionary containing face dimensions from Flutter/WebSocket
        Expected format: {
            'x': int,
            'y': int, 
            'width': int,
            'height': int,
            'frame_width': int,
            'frame_height': int,
            'custom_settings': dict (optional)
        }
    
    Returns:
        Dictionary with detection results
    """
    try:
        # Extract face dimensions
        face_x = face_data.get('x', 0)
        face_y = face_data.get('y', 0)
        face_width = face_data.get('width', 0)
        face_height = face_data.get('height', 0)
        frame_width = face_data.get('frame_width', 640)
        frame_height = face_data.get('frame_height', 480)
        
        # Get custom settings if provided
        custom_settings = face_data.get('custom_settings', {})
        
        # Default tolerance values (can be overridden by custom_settings)
        center_tolerance = custom_settings.get('center', 0.25)
        size_min = custom_settings.get('size_min', 0.15)
        size_max = custom_settings.get('size_max', 0.6)
        edge_margin = custom_settings.get('edge_margin', 0.1)
        
        # Check if face dimensions are valid
        if face_width <= 0 or face_height <= 0:
            return {
                'face_detected': False,
                'concentration_level': 'low',
                'message': 'No face detected',
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'analysis': {
                    'face_size_adequate': False,
                    'face_centered': False,
                    'face_distance_good': False,
                    'face_not_on_edge': False
                }
            }
        
        # Calculate face center
        face_center_x = face_x + face_width // 2
        face_center_y = face_y + face_height // 2
        
        # Calculate frame center
        frame_center_x = frame_width // 2
        frame_center_y = frame_height // 2
        
        # Analysis parameters
        analysis_result = {
            'face_size_adequate': False,
            'face_centered': False,
            'face_distance_good': False,
            'face_not_on_edge': False
        }
        
        # 1. Check if face size is adequate
        min_face_size = frame_width * size_min
        max_face_size = frame_width * size_max
        analysis_result['face_size_adequate'] = min_face_size <= face_width <= max_face_size
        
        # 2. Check if face is centered
        center_tolerance_x = frame_width * center_tolerance
        center_tolerance_y = frame_height * center_tolerance
        
        x_diff = abs(face_center_x - frame_center_x)
        y_diff = abs(face_center_y - frame_center_y)
        
        analysis_result['face_centered'] = (x_diff <= center_tolerance_x and y_diff <= center_tolerance_y)
        
        # 3. Check face distance (based on face size relative to frame)
        face_area_ratio = (face_width * face_height) / (frame_width * frame_height)
        analysis_result['face_distance_good'] = 0.02 <= face_area_ratio <= 0.3
        
        # 4. Check if face is not too close to edges
        analysis_result['face_not_on_edge'] = (
            face_x > frame_width * edge_margin and
            face_y > frame_height * edge_margin and
            (face_x + face_width) < frame_width * (1 - edge_margin) and
            (face_y + face_height) < frame_height * (1 - edge_margin)
        )
        
        # Calculate concentration level
        concentration_score = sum(analysis_result.values())
        
        # Determine concentration level
        if concentration_score >= 3:
            concentration_level = 'high'
            message = 'Excellent concentration detected'
        elif concentration_score >= 2:
            concentration_level = 'medium'
            message = 'Good concentration level'
        else:
            concentration_level = 'low'
            message = 'Poor concentration - please adjust position'
        
        return {
            'face_detected': True,
            'concentration_level': concentration_level,
            'concentration_score': concentration_score,
            'message': message,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'analysis': analysis_result,
            'face_position': {
                'x': face_x,
                'y': face_y,
                'width': face_width,
                'height': face_height,
                'center_x': face_center_x,
                'center_y': face_center_y
            },
            'recommendations': get_concentration_recommendations(analysis_result),
            'metrics': {
                'face_area_ratio': round(face_area_ratio, 4),
                'center_deviation_x': round(x_diff / frame_width, 4),
                'center_deviation_y': round(y_diff / frame_height, 4),
                'size_ratio': round(face_width / frame_width, 4)
            }
        }
        
    except Exception:
        logger.exception("Face concentration analysis failed")
        return {
            'face_detected': False,
            'concentration_level': 'error',
            'message': SAFE_ANALYSIS_ERROR_MESSAGE,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'analysis': {
                'face_size_adequate': False,
                'face_centered': False,
                'face_distance_good': False,
                'face_not_on_edge': False
            }
        }

def get_concentration_recommendations(analysis_result):
    """
    Provide recommendations based on analysis results
    """
    recommendations = []
    
    if not analysis_result['face_size_adequate']:
        recommendations.append("Adjust your distance from the camera")
    
    if not analysis_result['face_centered']:
        recommendations.append("Center your face in the frame")
    
    if not analysis_result['face_distance_good']:
        recommendations.append("Move to optimal distance from camera")
    
    if not analysis_result['face_not_on_edge']:
        recommendations.append("Ensure your full face is visible within frame boundaries")
    
    if not recommendations:
        recommendations.append("Perfect! Maintain your current position")
    
    return recommendations

# Optional: Function to validate face using OpenCV if image data is provided
def validate_face_with_opencv(image_data_base64):
    """
    Additional validation using OpenCV if image data is provided
    """
    try:
        # Decode base64 image
        image_data = base64.b64decode(image_data_base64)
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        return {
            'opencv_faces_detected': len(faces),
            'opencv_faces': faces.tolist() if len(faces) > 0 else []
        }
        
    except Exception:
        logger.exception("OpenCV face validation failed")
        return {
            'opencv_error': SAFE_ANALYSIS_ERROR_MESSAGE
        }
