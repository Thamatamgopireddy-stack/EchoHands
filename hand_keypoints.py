# -*- coding: utf-8 -*-
import cv2
import numpy as np
from typing import List, Tuple, Optional

class HandKeypointDetector:
    """Detect hand keypoints (joints) using contour analysis and hand pose estimation"""
    
    # Hand joint connections (skeleton)
    HAND_CONNECTIONS = [
        # Thumb
        (0, 1), (1, 2), (2, 3), (3, 4),
        # Index finger
        (0, 5), (5, 6), (6, 7), (7, 8),
        # Middle finger
        (0, 9), (9, 10), (10, 11), (11, 12),
        # Ring finger
        (0, 13), (13, 14), (14, 15), (15, 16),
        # Pinky
        (0, 17), (17, 18), (18, 19), (19, 20),
        # Palm connections
        (5, 9), (9, 13), (13, 17)
    ]
    
    def __init__(self):
        """Initialize hand keypoint detector"""
        pass
    
    def detect_hand_contours(self, frame: np.ndarray) -> Tuple[np.ndarray, List]:
        """Detect hand contours in frame"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        
        # Apply threshold to get binary image
        _, binary = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        return binary, contours
    
    def extract_hand_keypoints(self, contour: np.ndarray, num_keypoints: int = 21) -> Optional[np.ndarray]:
        """Extract hand keypoints from contour"""
        try:
            # Get contour moments
            M = cv2.moments(contour)
            
            if M["m00"] != 0:
                # Center of mass (palm root)
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Fit ellipse to get hand orientation
                if len(contour) >= 5:
                    ellipse = cv2.fitEllipse(contour)
                
                # Get contour extrema points (fingertips and hand base)
                extrema = []
                
                # Top-most point
                top = contour[contour[:, :, 1].argmin()][0]
                extrema.append(top)
                
                # Right-most point
                right = contour[contour[:, :, 0].argmax()][0]
                extrema.append(right)
                
                # Bottom-most point
                bottom = contour[contour[:, :, 1].argmax()][0]
                extrema.append(bottom)
                
                # Left-most point
                left = contour[contour[:, :, 0].argmin()][0]
                extrema.append(left)
                
                # Get convex hull for better hand representation
                hull = cv2.convexHull(contour)
                
                # Extract additional keypoints from hull
                hull_points = hull.reshape(-1, 2)
                
                # Sample keypoints along the hull
                step = max(1, len(hull_points) // 17)  # Get ~17 hull points
                sampled_points = hull_points[::step]
                
                # Pad or trim to get exactly num_keypoints
                keypoints = list(extrema)
                keypoints.extend(sampled_points.tolist())
                
                # Take first num_keypoints points
                keypoints = keypoints[:num_keypoints]
                
                # Pad with center point if needed
                while len(keypoints) < num_keypoints:
                    keypoints.append([cx, cy])
                
                return np.array(keypoints, dtype=np.float32)
        
        except Exception as e:
            print(f"Error extracting keypoints: {e}")
            return None
    
    def detect_and_draw_hand(self, frame: np.ndarray, min_area: int = 500) -> Tuple[np.ndarray, int, Optional[np.ndarray]]:
        """Detect hand and draw simple bounding box (no complex skeleton)"""
        binary, contours = self.detect_hand_contours(frame)
        
        hand_count = 0
        all_keypoints = None
        
        if contours:
            # Get the largest contour (likely the hand)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            
            for idx, contour in enumerate(contours[:2]):  # Process up to 2 hands
                area = cv2.contourArea(contour)
                
                if area >= min_area:
                    hand_count += 1
                    
                    # Extract keypoints (for gesture recognition, but don't draw them)
                    keypoints = self.extract_hand_keypoints(contour, num_keypoints=21)
                    
                    if keypoints is not None:
                        if all_keypoints is None:
                            all_keypoints = keypoints
                        
                        # Draw ONLY a simple bounding rectangle (clean and simple)
                        x, y, w_box, h_box = cv2.boundingRect(contour)
                        cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), (0, 255, 0), 2)
                        
                        # Add hand label text only
                        cv2.putText(frame, f"Hand {hand_count}", (x, y - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return frame, hand_count, all_keypoints
    
    @staticmethod
    def get_hand_pose_info(keypoints: np.ndarray) -> str:
        """Analyze hand pose from keypoints"""
        if keypoints is None or len(keypoints) < 5:
            return "Analyzing..."
        
        # Simple pose analysis based on keypoint positions
        fingertip_indices = [4, 8, 12, 16, 20]  # Thumb, Index, Middle, Ring, Pinky tips
        palm_center = keypoints[0]
        
        # Count how many fingers are extended
        extended_fingers = 0
        for tip_idx in fingertip_indices:
            if tip_idx < len(keypoints):
                tip = keypoints[tip_idx]
                # If fingertip is far from palm center, finger is extended
                distance = np.sqrt((tip[0] - palm_center[0])**2 + (tip[1] - palm_center[1])**2)
                if distance > 30:  # Threshold
                    extended_fingers += 1
        
        # Determine pose
        if extended_fingers == 0:
            return "✊ Fist"
        elif extended_fingers == 1:
            return "👆 One Finger"
        elif extended_fingers == 2:
            return "✌️ Two Fingers"
        elif extended_fingers >= 4:
            return "🖐 Open Hand"
        else:
            return "🤚 Partial Hand"
