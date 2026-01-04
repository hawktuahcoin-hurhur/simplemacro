import cv2
import numpy as np
import mss
from PIL import Image
import pyautogui
from typing import Tuple, Optional, List


class ImageDetector:
    """Handles image detection and screen capture operations"""
    
    def __init__(self, confidence_threshold: float = 0.8):
        """
        Initialize the image detector
        
        Args:
            confidence_threshold: Minimum confidence score for template matching (0-1)
        """
        self.confidence_threshold = confidence_threshold
        self.sct = mss.mss()
    
    def capture_screen(self, region: Optional[dict] = None) -> np.ndarray:
        """
        Capture a screenshot of the screen or a specific region
        
        Args:
            region: Optional dict with 'top', 'left', 'width', 'height' keys
                   If None, captures entire screen
        
        Returns:
            Screenshot as numpy array in BGR format
        """
        if region is None:
            monitor = self.sct.monitors[1]  # Primary monitor
        else:
            monitor = {
                "top": region["top"],
                "left": region["left"],
                "width": region["width"],
                "height": region["height"]
            }
        
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        # Convert BGRA to BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
    
    def load_template(self, template_path: str) -> np.ndarray:
        """
        Load a template image from file
        
        Args:
            template_path: Path to the template image file
        
        Returns:
            Template image as numpy array in BGR format
        """
        template = cv2.imread(template_path)
        if template is None:
            raise FileNotFoundError(f"Template image not found: {template_path}")
        return template
    
    def find_image(self, template: np.ndarray, region: Optional[dict] = None) -> Optional[Tuple[int, int, int, int]]:
        """
        Find a template image on the screen
        
        Args:
            template: Template image to search for (numpy array)
            region: Optional region to search in
        
        Returns:
            Tuple of (x, y, width, height) if found, None otherwise
        """
        screenshot = self.capture_screen(region)
        
        # Perform template matching
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= self.confidence_threshold:
            template_h, template_w = template.shape[:2]
            x, y = max_loc
            return (x, y, template_w, template_h)
        
        return None
    
    def find_all_images(self, template: np.ndarray, region: Optional[dict] = None, 
                       threshold: Optional[float] = None) -> List[Tuple[int, int, int, int]]:
        """
        Find all instances of a template image on the screen
        
        Args:
            template: Template image to search for
            region: Optional region to search in
            threshold: Optional custom threshold (overrides instance threshold)
        
        Returns:
            List of tuples (x, y, width, height) for all matches found
        """
        screenshot = self.capture_screen(region)
        threshold = threshold or self.confidence_threshold
        
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        template_h, template_w = template.shape[:2]
        
        # Find all locations above threshold
        locations = np.where(result >= threshold)
        matches = []
        
        for pt in zip(*locations[::-1]):
            matches.append((pt[0], pt[1], template_w, template_h))
        
        # Remove overlapping matches
        return self._non_max_suppression(matches, 0.3)
    
    def _non_max_suppression(self, boxes: List[Tuple[int, int, int, int]], 
                            overlap_thresh: float = 0.3) -> List[Tuple[int, int, int, int]]:
        """
        Apply non-maximum suppression to remove overlapping boxes
        
        Args:
            boxes: List of (x, y, width, height) tuples
            overlap_thresh: Maximum allowed overlap ratio
        
        Returns:
            Filtered list of boxes
        """
        if len(boxes) == 0:
            return []
        
        boxes_array = np.array(boxes)
        x1 = boxes_array[:, 0]
        y1 = boxes_array[:, 1]
        x2 = x1 + boxes_array[:, 2]
        y2 = y1 + boxes_array[:, 3]
        
        areas = boxes_array[:, 2] * boxes_array[:, 3]
        indices = np.arange(len(boxes_array))
        
        selected = []
        while len(indices) > 0:
            i = indices[0]
            selected.append(i)
            
            # Calculate overlap with remaining boxes
            xx1 = np.maximum(x1[i], x1[indices[1:]])
            yy1 = np.maximum(y1[i], y1[indices[1:]])
            xx2 = np.minimum(x2[i], x2[indices[1:]])
            yy2 = np.minimum(y2[i], y2[indices[1:]])
            
            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            
            overlap = (w * h) / areas[indices[1:]]
            indices = indices[np.where(overlap <= overlap_thresh)[0] + 1]
        
        return [boxes[i] for i in selected]
    
    def get_center(self, box: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """
        Get the center coordinates of a bounding box
        
        Args:
            box: Tuple of (x, y, width, height)
        
        Returns:
            Tuple of (center_x, center_y)
        """
        x, y, w, h = box
        return (x + w // 2, y + h // 2)
    
    def wait_for_image(self, template: np.ndarray, timeout: float = 10.0, 
                      check_interval: float = 0.5, region: Optional[dict] = None) -> Optional[Tuple[int, int, int, int]]:
        """
        Wait for an image to appear on screen
        
        Args:
            template: Template image to wait for
            timeout: Maximum time to wait in seconds
            check_interval: Time between checks in seconds
            region: Optional region to search in
        
        Returns:
            Box coordinates if found within timeout, None otherwise
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.find_image(template, region)
            if result is not None:
                return result
            time.sleep(check_interval)
        
        return None


def click_at(x: int, y: int, delay: float = 0.1):
    """
    Click at specific screen coordinates
    
    Args:
        x: X coordinate
        y: Y coordinate
        delay: Delay after clicking in seconds
    """
    pyautogui.click(x, y)
    import time
    time.sleep(delay)


def move_to(x: int, y: int, duration: float = 0.2):
    """
    Move mouse to specific coordinates
    
    Args:
        x: X coordinate
        y: Y coordinate
        duration: Time taken for movement in seconds
    """
    pyautogui.moveTo(x, y, duration=duration)
