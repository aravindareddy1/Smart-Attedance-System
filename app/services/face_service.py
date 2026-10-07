import abc
import base64
import io
import json
import logging
import os
import cv2
import numpy as np
from PIL import Image
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)


def decode_base64_image(base64_str: str) -> np.ndarray:
    """
    Decodes a base64 string (including data URI prefix) to an OpenCV BGR numpy array.
    """
    if ',' in base64_str:
        base64_str = base64_str.split(',', 1)[1]
    image_bytes = base64.b64decode(base64_str)
    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert('RGB')
    np_image = np.array(image)
    # Convert RGB to BGR for OpenCV
    bgr_image = cv2.cvtColor(np_image, cv2.COLOR_RGB2BGR)
    return bgr_image


class FaceRecognitionEngine(abc.ABC):
    """Abstract base class for face recognition engines."""

    @property
    @abc.abstractmethod
    def engine_name(self) -> str:
        pass

    @abc.abstractmethod
    def detect_faces(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects faces in BGR image.
        Returns list of dicts with: {'box': [x, y, w, h], 'confidence': float}
        """
        pass

    @abc.abstractmethod
    def validate_face_image(self, image_bgr: np.ndarray) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validates image for enrollment:
        - Image dimensions
        - Exactly one face
        - Blur detection (Laplacian variance)
        - Face size and brightness
        Returns (is_valid, error_message, face_metadata)
        """
        pass

    @abc.abstractmethod
    def extract_encoding(self, image_bgr: np.ndarray, box: Optional[List[int]] = None) -> Any:
        """
        Extracts face representation (vector or histogram) from image/box.
        """
        pass

    @abc.abstractmethod
    def match_candidate(self, candidate_encoding: Any, enrolled_items: List[Dict[str, Any]], threshold: float = 0.50) -> Optional[Dict[str, Any]]:
        """
        Matches candidate encoding against enrolled student items.
        Returns matching student dict with normalized match confidence or None.
        """
        pass

    def calculate_blur_score(self, image_bgr: np.ndarray) -> float:
        """Calculates Laplacian variance as a blur metric."""
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def calculate_brightness(self, image_bgr: np.ndarray) -> float:
        """Calculates average luminance in HSV."""
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        return float(np.mean(hsv[:, :, 2]))

    def check_liveness(self, current_frame: np.ndarray, previous_frame: Optional[np.ndarray]) -> Tuple[bool, str]:
        """
        Basic presentation attack heuristic:
        - Rejects identical frames (static image replay)
        - Checks for subtle natural motion between consecutive frames.
        """
        if previous_frame is None:
            return True, "Initial frame accepted"
        
        # Calculate pixel difference
        gray_curr = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        gray_prev = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
        
        if gray_curr.shape != gray_prev.shape:
            gray_prev = cv2.resize(gray_prev, (gray_curr.shape[1], gray_curr.shape[0]))
            
        diff = cv2.absdiff(gray_curr, gray_prev)
        non_zero_ratio = np.count_nonzero(diff > 15) / float(diff.size)
        
        if non_zero_ratio < 0.001:
            return False, "Possible static photo detected (no natural motion)"
        if non_zero_ratio > 0.90:
            return False, "Excessive camera shaking or sudden cut"
            
        return True, "Liveness check passed"


class FaceRecognitionLBPHEngine(FaceRecognitionEngine):
    """
    OpenCV Haar Cascade + LBPH (Local Binary Patterns Histograms) Face Recognition Engine.
    Robust native fallback that runs without dlib / C++ build dependencies.
    """

    def __init__(self):
        self._cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self._face_cascade = cv2.CascadeClassifier(self._cascade_path)
        self._recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        self._trained = False

    @property
    def engine_name(self) -> str:
        return 'OpenCV-LBPH'

    def detect_faces(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        results = []
        for (x, y, w, h) in faces:
            results.append({
                'box': [int(x), int(y), int(w), int(h)],
                'confidence': 1.0
            })
        return results

    def validate_face_image(self, image_bgr: np.ndarray) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if image_bgr is None or image_bgr.size == 0:
            return False, "Invalid or empty image", None

        h, w = image_bgr.shape[:2]
        if h < 100 or w < 100:
            return False, "Image resolution is too low. Minimum 100x100 required.", None

        # Blur check
        blur_score = self.calculate_blur_score(image_bgr)
        if blur_score < 45.0:
            return False, f"Enrollment rejected: Image is too blurry (score: {blur_score:.1f} < 45). Please keep the camera steady.", None

        # Brightness check
        brightness = self.calculate_brightness(image_bgr)
        if brightness < 30:
            return False, "Enrollment rejected: Image is too dark. Please ensure adequate lighting.", None
        if brightness > 235:
            return False, "Enrollment rejected: Image is overexposed. Please adjust lighting.", None

        # Detect face
        faces = self.detect_faces(image_bgr)
        if len(faces) == 0:
            return False, "No face detected in the image. Please position your face clearly in the frame.", None
        if len(faces) > 1:
            return False, f"Multiple faces detected ({len(faces)}). Exactly one face is required for enrollment.", None

        face_box = faces[0]['box']
        fw, fh = face_box[2], face_box[3]
        if fw < 60 or fh < 60:
            return False, "Face is too small in the frame. Please move closer to the camera.", None

        metadata = {
            'box': face_box,
            'blur_score': blur_score,
            'brightness': brightness,
            'quality_score': round(min(1.0, blur_score / 200.0), 2)
        }
        return True, "Valid face image", metadata

    def extract_encoding(self, image_bgr: np.ndarray, box: Optional[List[int]] = None) -> Any:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        if box:
            x, y, w, h = box
            # Clip coordinates
            img_h, img_w = gray.shape
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(img_w, x + w), min(img_h, y + h)
            face_roi = gray[y1:y2, x1:x2]
        else:
            face_roi = gray
            
        if face_roi.size == 0:
            return None
            
        # Standardize face ROI size for LBPH comparison
        face_resized = cv2.resize(face_roi, (120, 120))
        # Store as base64 string representation of the 120x120 grayscale ROI
        return base64.b64encode(face_resized.tobytes()).decode('utf-8')

    def match_candidate(self, candidate_encoding: Any, enrolled_items: List[Dict[str, Any]], threshold: float = 65.0) -> Optional[Dict[str, Any]]:
        """
        Trains or uses cached LBPH matcher over enrolled items.
        enrolled_items: list of {'student_id': int, 'name': str, 'roll_no': str, 'encoding': str}
        """
        if not candidate_encoding or not enrolled_items:
            return None

        candidate_bytes = base64.b64decode(candidate_encoding)
        candidate_roi = np.frombuffer(candidate_bytes, dtype=np.uint8).reshape((120, 120))

        # Re-train local LBPH model on enrolled student faces
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        faces = []
        labels = []
        label_to_student = {}
        label_idx = 1

        for item in enrolled_items:
            try:
                enc_bytes = base64.b64decode(item['encoding'])
                face_arr = np.frombuffer(enc_bytes, dtype=np.uint8).reshape((120, 120))
                faces.append(face_arr)
                labels.append(label_idx)
                label_to_student[label_idx] = item
                label_idx += 1
            except Exception as e:
                logger.warning(f"Error decoding enrolled face item: {e}")

        if not faces:
            return None

        recognizer.train(faces, np.array(labels))
        predicted_label, lbph_distance = recognizer.predict(candidate_roi)

        # LBPH distance: 0 is exact match, 100+ is distant. Default confidence threshold is 65-75.
        # Normalize to 0.0 - 1.0 match confidence
        normalized_confidence = max(0.0, min(1.0, 1.0 - (lbph_distance / 100.0)))
        
        # If distance is within threshold (e.g. <= 70)
        max_dist_allowed = threshold if threshold > 1.0 else (1.0 - threshold) * 100.0
        if lbph_distance <= max_dist_allowed and predicted_label in label_to_student:
            student = label_to_student[predicted_label]
            return {
                'student_id': student['student_id'],
                'name': student['name'],
                'roll_no': student['roll_no'],
                'confidence': round(normalized_confidence, 2),
                'raw_distance': round(float(lbph_distance), 2)
            }

        return None


class FaceRecognitionDlibEngine(FaceRecognitionEngine):
    """
    Dlib 128-d Face Recognition Engine (using face_recognition package if available).
    """

    def __init__(self):
        import face_recognition
        self._fr = face_recognition

    @property
    def engine_name(self) -> str:
        return 'dlib-face_recognition'

    def detect_faces(self, image_bgr: np.ndarray) -> List[Dict[str, Any]]:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        locations = self._fr.face_locations(rgb)
        results = []
        for (top, right, bottom, left) in locations:
            results.append({
                'box': [int(left), int(top), int(right - left), int(bottom - top)],
                'confidence': 1.0
            })
        return results

    def validate_face_image(self, image_bgr: np.ndarray) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if image_bgr is None or image_bgr.size == 0:
            return False, "Invalid or empty image", None

        h, w = image_bgr.shape[:2]
        if h < 100 or w < 100:
            return False, "Image resolution is too low. Minimum 100x100 required.", None

        blur_score = self.calculate_blur_score(image_bgr)
        if blur_score < 45.0:
            return False, f"Enrollment rejected: Image is too blurry ({blur_score:.1f}). Please hold camera steady.", None

        faces = self.detect_faces(image_bgr)
        if len(faces) == 0:
            return False, "No face detected in the image.", None
        if len(faces) > 1:
            return False, f"Multiple faces detected ({len(faces)}). Please enroll with only one face in frame.", None

        return True, "Valid face image", {
            'box': faces[0]['box'],
            'blur_score': blur_score,
            'quality_score': round(min(1.0, blur_score / 200.0), 2)
        }

    def extract_encoding(self, image_bgr: np.ndarray, box: Optional[List[int]] = None) -> Any:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        if box:
            x, y, w, h = box
            known_loc = [(y, x + w, y + h, x)]
            encodings = self._fr.face_encodings(rgb, known_face_locations=known_loc)
        else:
            encodings = self._fr.face_encodings(rgb)

        if encodings:
            return json.dumps(encodings[0].tolist())
        return None

    def match_candidate(self, candidate_encoding: Any, enrolled_items: List[Dict[str, Any]], threshold: float = 0.50) -> Optional[Dict[str, Any]]:
        if not candidate_encoding or not enrolled_items:
            return None

        if isinstance(candidate_encoding, str):
            candidate_vec = np.array(json.loads(candidate_encoding))
        else:
            candidate_vec = np.array(candidate_encoding)

        known_encodings = []
        valid_items = []
        for item in enrolled_items:
            try:
                vec = np.array(json.loads(item['encoding']))
                known_encodings.append(vec)
                valid_items.append(item)
            except Exception:
                continue

        if not known_encodings:
            return None

        distances = self._fr.face_distance(known_encodings, candidate_vec)
        min_idx = int(np.argmin(distances))
        best_dist = float(distances[min_idx])

        if best_dist <= threshold:
            student = valid_items[min_idx]
            # Normalize confidence: distance 0.0 -> 100%, threshold -> ~60%
            confidence = max(0.0, min(1.0, 1.0 - (best_dist / (threshold * 2.0))))
            return {
                'student_id': student['student_id'],
                'name': student['name'],
                'roll_no': student['roll_no'],
                'confidence': round(confidence, 2),
                'raw_distance': round(best_dist, 3)
            }
        return None


# Engine Singleton & Factory
_active_engine: Optional[FaceRecognitionEngine] = None


def get_face_engine(preferred: str = 'auto') -> FaceRecognitionEngine:
    global _active_engine
    if _active_engine is not None:
        return _active_engine

    if preferred in ('auto', 'dlib'):
        try:
            _active_engine = FaceRecognitionDlibEngine()
            logger.info("Face recognition initialized with primary Dlib engine.")
            return _active_engine
        except Exception as e:
            logger.info(f"Dlib not available ({e}). Falling back to OpenCV-LBPH engine.")

    _active_engine = FaceRecognitionLBPHEngine()
    logger.info("Face recognition initialized with native OpenCV-LBPH fallback engine.")
    return _active_engine


class ConsecutiveMatchTracker:
    """
    Session-level match buffer.
    Requires at least 2 consecutive positive recognitions of the same student
    before confirming attendance to prevent single-frame false positives.
    """
    def __init__(self, required_matches: int = 2):
        self.required_matches = required_matches
        self._history: Dict[int, int] = {}  # student_id -> consecutive count

    def register_match(self, student_id: int) -> bool:
        """
        Returns True if student reached the required consecutive match count.
        """
        count = self._history.get(student_id, 0) + 1
        self._history[student_id] = count
        if count >= self.required_matches:
            return True
        return False

    def reset_student(self, student_id: int):
        if student_id in self._history:
            del self._history[student_id]

    def clear(self):
        self._history.clear()
