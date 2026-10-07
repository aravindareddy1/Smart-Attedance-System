import base64
import numpy as np
import cv2
from app.services.face_service import (
    decode_base64_image, get_face_engine, ConsecutiveMatchTracker, FaceRecognitionLBPHEngine
)


def test_decode_base64_image():
    # Create a small 100x100 white test image
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    _, buffer = cv2.imencode('.jpg', img)
    b64_str = "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')

    decoded = decode_base64_image(b64_str)
    assert isinstance(decoded, np.ndarray)
    assert decoded.shape == (100, 100, 3)


def test_consecutive_match_tracker():
    tracker = ConsecutiveMatchTracker(required_matches=2)
    student_id = 42

    # 1st match -> False (Not yet confirmed)
    assert tracker.register_match(student_id) is False

    # 2nd match -> True (Confirmed)
    assert tracker.register_match(student_id) is True

    # 3rd match -> True (Maintains confirmed)
    assert tracker.register_match(student_id) is True

    # Reset
    tracker.reset_student(student_id)
    assert tracker.register_match(student_id) is False


def test_blur_and_brightness_calculation():
    engine = FaceRecognitionLBPHEngine()
    
    # Sharp image with distinct pattern
    sharp_img = np.zeros((100, 100, 3), dtype=np.uint8)
    sharp_img[::2, ::2] = 255
    sharp_score = engine.calculate_blur_score(sharp_img)
    assert sharp_score > 50.0

    # Flat image (very blurry / zero variance)
    flat_img = np.ones((100, 100, 3), dtype=np.uint8) * 128
    flat_score = engine.calculate_blur_score(flat_img)
    assert flat_score < 10.0

    # Brightness calculation
    brightness = engine.calculate_brightness(flat_img)
    assert 120 <= brightness <= 135


def test_liveness_heuristic():
    engine = FaceRecognitionLBPHEngine()
    frame1 = np.ones((100, 100, 3), dtype=np.uint8) * 100

    # Identical frame -> should detect static replay
    is_live, msg = engine.check_liveness(frame1, frame1)
    assert is_live is False
    assert "static photo" in msg.lower()

    # Subtle natural movement frame
    frame2 = frame1.copy()
    frame2[20:40, 20:40] = 150
    is_live2, msg2 = engine.check_liveness(frame2, frame1)
    assert is_live2 is True
    assert "passed" in msg2.lower()
