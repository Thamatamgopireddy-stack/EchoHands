# -*- coding: utf-8 -*-
"""Simple Hand Detection - Clean visualization"""

import cv2
from hand_keypoints import HandKeypointDetector  # type: ignore

# Initialize hand keypoint detector
detector = HandKeypointDetector()

cap = cv2.VideoCapture(0)

print("=" * 60)
print("🖐️  SIMPLE HAND DETECTION")
print("=" * 60)
print("Press ESC to exit.\n")
print("What you see:")
print("  🟢 Green box  = Hand detected")
print("  Text label   = Hand number")
print("=" * 60 + "\n")

frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1
    
    # Flip for mirror view
    frame = cv2.flip(frame, 1)

    # Detect hand (SIMPLE - just box, no skeleton/points)
    frame, hand_count, keypoints = detector.detect_and_draw_hand(frame, min_area=500)
    
    if hand_count > 0:
        # Get pose info
        pose = HandKeypointDetector.get_hand_pose_info(keypoints)
        
        # Display pose
        text = f"Pose: {pose} | Hands: {hand_count}"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "No hands detected. Move your hand in front of camera.", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.imshow("Hand Detection [SIMPLE]", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC key
        break

cap.release()
cv2.destroyAllWindows()
print("\n" + "=" * 60)
print("✅ Hand detection stopped")
print("=" * 60)