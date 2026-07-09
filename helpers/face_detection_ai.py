import numpy as np
from datetime import datetime
import time



class FaceDetectionAI:
    def __init__(self):
        """Initialize the Face Detection AI for dimensions-based validation"""
        self.last_detection_time = None
        self.detection_history = []
        self.max_history = 50
        
        # Face positioning validation settings
        self.positioning_rules = {
            'center_tolerance': 0.15,  # 15% tolerance from center
            'size_min_ratio': 0.08,   # Face should be at least 8% of frame
            'size_max_ratio': 0.6,    # Face should not exceed 60% of frame
            'aspect_ratio_tolerance': 0.3,  # Face aspect ratio tolerance
            'edge_margin': 0.05       # 5% margin from edges
        }
    
    def validate_face_dimensions(self, face_dimensions, frame_dimensions, settings=None):
        """
        Validate face dimensions and positioning
        
        Args:
            face_dimensions: dict with 'x', 'y', 'width', 'height' keys
            frame_dimensions: dict with 'width' and 'height' keys
            settings: dict with validation settings (optional)
            
        Returns:
            dict: Validation results with positioning analysis
        """
        try:
            # Validate input parameters
            validation_result = self._validate_input_parameters(face_dimensions, frame_dimensions)
            if not validation_result['is_valid']:
                return validation_result
            
            # Default settings
            default_settings = {
                'validate_positioning': True,
                'strict_mode': False,
                'custom_tolerance': None
            }
            
            if settings:
                default_settings.update(settings)
            
            # Extract dimensions
            face_x = face_dimensions['x']
            face_y = face_dimensions['y']
            face_width = face_dimensions['width']
            face_height = face_dimensions['height']
            frame_width = frame_dimensions['width']
            frame_height = frame_dimensions['height']
            
            # Create face data object
            face_data = {
                'id': 0,
                'x': int(face_x),
                'y': int(face_y),
                'width': int(face_width),
                'height': int(face_height),
                'center_x': int(face_x + face_width/2),
                'center_y': int(face_y + face_height/2),
                'confidence': self._calculate_confidence(face_width, face_height, frame_width, frame_height)
            }
            
            # Validate positioning
            positioning_analysis = self._validate_face_positioning(
                face_data, frame_width, frame_height, default_settings
            )
            
            # Determine overall status
            if positioning_analysis['is_valid']:
                status = "optimal_position"
                message = "🎯 Perfect face position!"
                alert_level = "success"
            else:
                status = "needs_adjustment"
                message = "📐 Position needs adjustment"
                alert_level = "info"
            
            # Update detection history
            self._update_detection_history(1, status)
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'face_count': 1,
                'message': message,
                'status': status,
                'alert_level': alert_level,
                'face_data': face_data,
                'positioning': positioning_analysis,
                'frame_dimensions': {
                    'width': frame_width,
                    'height': frame_height
                },
                'guidelines': self._get_positioning_guidelines(frame_width, frame_height),
                'detection_history': self.detection_history[-5:],
                'processing_time': self._get_processing_time(),
                'settings_used': default_settings
            }
            
            return result
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'face_count': 0,
                'message': f"Validation error: {str(e)}",
                'status': "error",
                'alert_level': "error",
                'face_data': None,
                'positioning': {'is_valid': False, 'errors': [str(e)]},
                'processing_time': self._get_processing_time()
            }
    
    def _validate_input_parameters(self, face_dimensions, frame_dimensions):
        """Validate input parameters"""
        errors = []
        
        # Check face_dimensions
        required_face_keys = ['x', 'y', 'width', 'height']
        for key in required_face_keys:
            if key not in face_dimensions:
                errors.append(f"Missing face dimension: {key}")
            elif not isinstance(face_dimensions[key], (int, float)):
                errors.append(f"Invalid face dimension type for {key}: expected number")
            elif face_dimensions[key] < 0:
                errors.append(f"Invalid face dimension value for {key}: cannot be negative")
        
        # Check frame_dimensions
        required_frame_keys = ['width', 'height']
        for key in required_frame_keys:
            if key not in frame_dimensions:
                errors.append(f"Missing frame dimension: {key}")
            elif not isinstance(frame_dimensions[key], (int, float)):
                errors.append(f"Invalid frame dimension type for {key}: expected number")
            elif frame_dimensions[key] <= 0:
                errors.append(f"Invalid frame dimension value for {key}: must be positive")
        
        # Check if face is within frame bounds
        if not errors:  # Only check if basic validation passed
            if (face_dimensions['x'] + face_dimensions['width']) > frame_dimensions['width']:
                errors.append("Face extends beyond frame width")
            if (face_dimensions['y'] + face_dimensions['height']) > frame_dimensions['height']:
                errors.append("Face extends beyond frame height")
        
        if errors:
            return {
                'is_valid': False,
                'errors': errors,
                'timestamp': datetime.now().isoformat(),
                'status': 'input_validation_failed',
                'alert_level': 'error'
            }
        
        return {'is_valid': True}
    
    def _validate_face_positioning(self, face_data, frame_width, frame_height, settings=None):
        """Validate face positioning within frame"""
        issues = []
        suggestions = []
        
        # Calculate relative positions
        face_center_x = face_data['center_x']
        face_center_y = face_data['center_y']
        face_width = face_data['width']
        face_height = face_data['height']
        
        frame_center_x = frame_width / 2
        frame_center_y = frame_height / 2
        
        # Relative position (0-1 range)
        rel_x = face_center_x / frame_width
        rel_y = face_center_y / frame_height
        
        # Face size ratio
        face_area = face_width * face_height
        frame_area = frame_width * frame_height
        size_ratio = face_area / frame_area
        
        # Use custom tolerance if provided
        center_tolerance = self.positioning_rules['center_tolerance']
        if settings and settings.get('custom_tolerance'):
            center_tolerance = settings['custom_tolerance'].get('center', center_tolerance)
        
        # Check horizontal centering
        x_deviation = abs(rel_x - 0.5)
        if x_deviation > center_tolerance:
            issues.append('Face not horizontally centered')
            if rel_x < 0.5:
                suggestions.append('Move slightly to the right')
            else:
                suggestions.append('Move slightly to the left')
        
        # Check vertical centering
        y_deviation = abs(rel_y - 0.5)
        if y_deviation > center_tolerance:
            issues.append('Face not vertically centered')
            if rel_y < 0.5:
                suggestions.append('Move slightly down')
            else:
                suggestions.append('Move slightly up')
        
        # Check face size
        if size_ratio < self.positioning_rules['size_min_ratio']:
            issues.append('Face too small in frame')
            suggestions.append('Move closer to camera')
        elif size_ratio > self.positioning_rules['size_max_ratio']:
            issues.append('Face too large in frame')
            suggestions.append('Move further from camera')
        
        # Check edge margins
        edge_margin = self.positioning_rules['edge_margin']
        left_margin = face_data['x'] / frame_width
        right_margin = (frame_width - (face_data['x'] + face_width)) / frame_width
        top_margin = face_data['y'] / frame_height
        bottom_margin = (frame_height - (face_data['y'] + face_height)) / frame_height
        
        if min(left_margin, right_margin, top_margin, bottom_margin) < edge_margin:
            issues.append('Face too close to frame edges')
            suggestions.append('Center face better in frame')
        
        # Check face aspect ratio (should be roughly rectangular)
        face_aspect_ratio = face_width / face_height
        if abs(face_aspect_ratio - 0.75) > self.positioning_rules['aspect_ratio_tolerance']:
            issues.append('Unusual face aspect ratio detected')
            suggestions.append('Face the camera directly')
        
        # Calculate positioning score (0-100)
        positioning_score = self._calculate_positioning_score(
            x_deviation, y_deviation, size_ratio, face_aspect_ratio, 
            min(left_margin, right_margin, top_margin, bottom_margin))
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'suggestions': suggestions,
            'positioning_score': positioning_score,
            'metrics': {
                'center_deviation_x': round(x_deviation, 3),
                'center_deviation_y': round(y_deviation, 3),
                'size_ratio': round(size_ratio, 3),
                'aspect_ratio': round(face_aspect_ratio, 3),
                'edge_margins': {
                    'left': round(left_margin, 3),
                    'right': round(right_margin, 3),
                    'top': round(top_margin, 3),
                    'bottom': round(bottom_margin, 3)
                }
            }
        }
    
    def _calculate_positioning_score(self, x_dev, y_dev, size_ratio, aspect_ratio, min_margin):
        """Calculate positioning score from 0-100"""
        try:
            # Center positioning score (0-40 points)
            center_score = max(0, 40 - (x_dev + y_dev) * 100)
            
            # Size score (0-30 points)
            optimal_size = 0.25  # 25% of frame
            size_score = max(0, 30 - abs(size_ratio - optimal_size) * 100)
            
            # Aspect ratio score (0-15 points)
            optimal_aspect = 0.75
            aspect_score = max(0, 15 - abs(aspect_ratio - optimal_aspect) * 50)
            
            # Margin score (0-15 points)
            margin_score = min(15, min_margin * 300)
            
            total_score = center_score + size_score + aspect_score + margin_score
            return round(min(100, max(0, total_score)), 1)
            
        except:
            return 0.0
    
    def _get_positioning_guidelines(self, frame_width, frame_height):
        """Get positioning guidelines for the current frame dimensions"""
        center_zone = {
            'x': int(frame_width * 0.3),
            'y': int(frame_height * 0.25),
            'width': int(frame_width * 0.4),
            'height': int(frame_height * 0.5)
        }
        
        optimal_face_size = {
            'min_area_ratio': self.positioning_rules['size_min_ratio'],
            'max_area_ratio': self.positioning_rules['size_max_ratio'],
            'min_width': int(frame_width * 0.15),
            'max_width': int(frame_width * 0.6),
            'min_height': int(frame_height * 0.2),
            'max_height': int(frame_height * 0.7)
        }
        
        return {
            'frame_dimensions': {'width': frame_width, 'height': frame_height},
            'center_zone': center_zone,
            'optimal_face_size': optimal_face_size,
            'positioning_rules': self.positioning_rules.copy(),
            'instructions': [
                '1. Position your face in the center of the frame',
                '2. Ensure your entire face is visible',
                '3. Face should occupy 8-60% of the frame area',
                '4. Maintain equal spacing from all edges',
                '5. Look directly at the camera',
                '6. Ensure good lighting on your face'
            ]
        }
    
    def _calculate_confidence(self, face_width, face_height, frame_width, frame_height):
        """Calculate confidence score based on face characteristics"""
        try:
            # Size-based confidence
            face_area = face_width * face_height
            frame_area = frame_width * frame_height
            size_ratio = face_area / frame_area
            
            # Optimal size ratio gives higher confidence
            if 0.1 <= size_ratio <= 0.4:
                size_confidence = 0.9
            elif 0.05 <= size_ratio <= 0.6:
                size_confidence = 0.7
            else:
                size_confidence = 0.4
            
            # Aspect ratio confidence
            aspect_ratio = face_width / face_height
            if 0.6 <= aspect_ratio <= 1.0:
                aspect_confidence = 0.9
            else:
                aspect_confidence = 0.6
            
            # Combined confidence
            confidence = (size_confidence + aspect_confidence) / 2
            return round(min(0.99, max(0.1, confidence)), 2)
            
        except:
            return 0.5
    
    def _update_detection_history(self, face_count, status):
        """Update detection history for analytics"""
        try:
            self.detection_history.append({
                'face_count': face_count,
                'status': status,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep only recent history
            if len(self.detection_history) > self.max_history:
                self.detection_history = self.detection_history[-self.max_history:]
                
        except Exception:
            pass
    
    def _get_processing_time(self):
        """Get processing time since last detection"""
        try:
            current_time = time.time()
            if self.last_detection_time:
                processing_time = current_time - self.last_detection_time
            else:
                processing_time = 0
            
            self.last_detection_time = current_time
            return round(processing_time * 1000, 2)  # Convert to milliseconds
            
        except:
            return 0
    
    def get_detection_stats(self):
        """Get detection statistics and analytics"""
        try:
            if not self.detection_history:
                return {
                    'total_detections': 0,
                    'success_rate': 0,
                    'average_faces': 0,
                    'positioning_success_rate': 0,
                    'recent_activity': []
                }
            
            total_detections = len(self.detection_history)
            successful_detections = len([h for h in self.detection_history if h['face_count'] > 0])
            optimal_positions = len([h for h in self.detection_history if h['status'] == 'optimal_position'])
            face_counts = [h['face_count'] for h in self.detection_history]
            
            return {
                'total_detections': total_detections,
                'success_rate': round((successful_detections / total_detections) * 100, 1),
                'average_faces': round(sum(face_counts) / total_detections, 2),
                'positioning_success_rate': round((optimal_positions / total_detections) * 100, 1),
                'status_breakdown': self._get_status_breakdown(),
                'recent_activity': self.detection_history[-10:]
            }
            
        except Exception as e:
            return {
                'total_detections': 0,
                'success_rate': 0,
                'error': str(e)
            }
    
    def _get_status_breakdown(self):
        """Get breakdown of detection statuses"""
        try:
            status_counts = {}
            for entry in self.detection_history:
                status = entry['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return status_counts
        except:
            return {}
    
    def batch_validate_faces(self, faces_list, frame_dimensions, settings=None):
        """
        Validate multiple face dimensions at once
        
        Args:
            faces_list: list of face dimension dictionaries
            frame_dimensions: dict with 'width' and 'height'
            settings: validation settings
            
        Returns:
            dict: Batch validation results
        """
        try:
            results = []
            for i, face_dims in enumerate(faces_list):
                result = self.validate_face_dimensions(face_dims, frame_dimensions, settings)
                result['face_index'] = i
                results.append(result)
            
            # Summary statistics
            valid_faces = [r for r in results if r.get('positioning', {}).get('is_valid', False)]
            avg_score = sum([r.get('positioning', {}).get('positioning_score', 0) for r in results]) / len(results) if results else 0
            
            return {
                'timestamp': datetime.now().isoformat(),
                'total_faces': len(faces_list),
                'valid_faces': len(valid_faces),
                'average_positioning_score': round(avg_score, 1),
                'results': results,
                'batch_summary': {
                    'success_rate': round((len(valid_faces) / len(faces_list)) * 100, 1) if faces_list else 0,
                    'needs_adjustment': len(faces_list) - len(valid_faces)
                }
            }
            
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'error': f"Batch validation failed: {str(e)}",
                'total_faces': 0,
                'valid_faces': 0
            }
