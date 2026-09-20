# -*- coding: utf-8 -*-
import cv2

# Try different camera indexes
cap = None
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"[OK] Camera opened (index {i}). Press ESC to close.")
        break
    cap.release()

if cap is None or not cap.isOpened():
    print("[ERROR] No camera found. Check if camera is connected.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] Frame not received.")
        break

    # 🔄 FIX: Flip horizontally (mirror correction)
    frame = cv2.flip(frame, 1)

    cv2.imshow("Camera Test", frame)

    if cv2.waitKey(1) & 0xFF == 27:   # ESC
        break

cap.release()
cv2.destroyAllWindows()
