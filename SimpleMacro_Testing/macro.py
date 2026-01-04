"""
Roblox Image Detection Macro
Main script for running the macro with image detection
"""

import json
import time
import os
import keyboard
import pyautogui
from pathlib import Path
from image_utils import ImageDetector, click_at, move_to
try:
    import pygetwindow as gw
except ImportError:
    gw = None


class RobloxMacro:
    """Main macro class for Roblox automation"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the macro
        
        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.detector = ImageDetector(
            confidence_threshold=self.config["detection"]["confidence_threshold"]
        )
        self.running = False
        self.paused = False
        self.templates = {}
        self.initial_sequence_done = False
        self._load_templates()
        self._setup_hotkeys()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def _load_templates(self):
        """Load all template images from the images folder"""
        template_folder = Path(self.config["images"]["template_folder"])
        
        if not template_folder.exists():
            print(f"Warning: Template folder '{template_folder}' not found")
            return
        
        image_files = list(template_folder.glob("*.png")) + list(template_folder.glob("*.jpg"))
        
        for img_path in image_files:
            if img_path.name == "README.md":
                continue
            
            try:
                template_name = img_path.stem  # Filename without extension
                self.templates[template_name] = self.detector.load_template(str(img_path))
                print(f"Loaded template: {template_name}")
            except Exception as e:
                print(f"Failed to load {img_path.name}: {e}")
        
        if not self.templates:
            print("No template images found! Please add images to the 'images' folder.")
    
    def _setup_hotkeys(self):
        """Setup keyboard hotkeys for controlling the macro"""
        keyboard.add_hotkey(self.config["hotkeys"]["start"], self.start)
        keyboard.add_hotkey(self.config["hotkeys"]["pause"], self.toggle_pause)
        keyboard.add_hotkey(self.config["hotkeys"]["stop"], self.stop)
    
    def start(self):
        """Start the macro"""
        if nif not self._check_roblox_running():
                print("\n⚠️  Roblox is not detected! Please start Roblox first.")
                return
            
            self.running = True
            self.paused = False
            self.initial_sequence_done = False
            print("\n=== Macro Started ===")
            print(f"Press {self.config['hotkeys']['pause'].upper()} to pause")
            print(f"Press {self.config['hotkeys']['stop'].upper()} to stop\n")
            self._run_initial_sequence()
            print(f"Press {self.config['hotkeys']['stop'].upper()} to stop\n")
    
    def toggle_pause(self):
        """Toggle pause state"""
        if self.running:
            self.paused = not self.paused
            if self.paused:
                print("=== Macro Paused ===")
            else:
                print("=== Macro Resumed ===")
    self.initial_sequence_done = False
            
    def stop(self):
        """Stop the macro"""
        if self.running:
            self.running = False
            self.paused = False
            print("\n=== Macro Stopped ===")
    
    def find_and_click(self, template_name: str, offset_x: int = 0, offset_y: int = 0) -> bool:
        """
        Find an image and click on it
        
        Args:
            template_name: Name of the template to find (without extension)
            offset_x: X offset from center to click
            offset_y: Y offset from center to click
        
        Returns:
            True if image was found and clicked, False otherwise
        """
        if template_name not in self.templates:
            print(f"Template '{template_name}' not found")
            return False
        
        template = self.templates[template_name]
        box = self.detector.find_image(template, self.config["detection"].get("region"))
        
        if box:
            center_x, center_y = self.detector.get_center(box)
            click_x = center_x + offset_x
            click_y = center_y + offset_y
            click_at(click_x, click_y, self.config["actions"]["click_delay"])
            print(f"Clicked on '{template_name}' at ({click_x}, {click_y})")
            return True
        
        return False
    
    def wait_for_image(self, template_name: str, timeout: float = 10.0) -> bool:
        """
        Wait for an image to appear
        
        Args:
            template_name: Name of the template to wait for
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if image appeared, False if timeout
        """
        if template_name not in self.templates:
            print(f"Template '{template_name}' not found")
            return False
        
        template = self.templates[template_name]
        scan_interval = self.config["detection"]["scan_interval"]
        region = self.config["detection"].get("region")
        
        box = self.detector.wait_for_image(template, timeout, scan_interval, region)
        
        _check_roblox_running(self) -> bool:
        """
        Check if Roblox is currently running
        
        Returns:
            True if Roblox window is found, False otherwise
        """
        if gw is None:
            print("⚠️  pygetwindow not installed, skipping Roblox detection")
            return True  # Allow to continue if library not available
        
        try:
            windows = gw.getAllTitles()
            roblox_found = any('Roblox' in title or 'roblox' in title for title in windows)
            if roblox_found:
                print("✓ Roblox detected")
            return roblox_found
        except Exception as e:
            print(f"⚠️  Could not check for Roblox: {e}")
            return True  # Allow to continue on error
    
    def _run_initial_sequence(self):
        """
        Run the initial sequence when macro starts:
        1. Hold 'I' key
        2. Drag mouse all the way down
        3. Hold 'O' key
        """
        print("Running initial sequence...")
        
        try:
            # Get screen dimensions
            screen_width, screen_height = pyautogui.size()
            
            # Hold 'I' key
            print("Holding 'I' key...")
            keyboard.press('i')
            time.sleep(0.5)
            keyboard.release('i')
            time.sleep(0.3)
            
            # Drag mouse all the way down
            print("Dragging mouse down...")
            current_x, current_y = pyautogui.position()
            # Drag from current position to bottom of screen
            pyautogui.moveTo(current_x, screen_height - 50, duration=0.5)
            time.sleep(0.3)
            
            # Hold 'O' key
            print("Holding 'O' key...")
            keyboard.press('o')
            time.sleep(0.5)
            keyboard.release('o')
            time.sleep(0.3)
            
            self.initial_sequence_done = True
            print("✓ Initial sequence completed\n")
            
        except Exception as e:
            print(f"Error during initial sequence: {e}")
            self.initial_sequence_done = True  # Continue anyway
    
    def if box:
            print(f"Found '{template_name}'")
            return True
        else:
            print(f"Timeout waiting for '{template_name}'")
            return False
    
    def image_exists(self, template_name: str) -> bool:
        """
        Check if an image exists on screen
        
        Args:
            template_name: Name of the template to check
        
        Returns:
            True if image exists, False otherwise
        """
        if template_name not in self.templates:
            return False
        
        template = self.templates[template_name]
        box = self.detector.find_image(template, self.config["detection"].get("region"))
        return box is not None
    
    def macro_logic(self):
        """
        Main macro logic - customize this based on your needs
        This is an example implementation
        """
        # Example: Simple pattern
        # 1. Wait for a specific button to appear
        # 2. Click it
        # 3. Wait and repeat
        
        # Example template names (replace with your actual template names):
        # - "play_button": A play or start button
        # - "reward": A reward to collect
        # - "close_button": A popup close button
        
        print("Running macro logic...")
        
        # Example 1: Click on a button if it exists
        if self.image_exists("play_button"):
            self.find_and_click("play_button")
            time.sleep(1)
        
        # Example 2: Wait for and click a reward
        if self.wait_for_image("reward", timeout=5):
            self.find_and_click("reward")
        
        # Example 3: Close popups
        if self.image_exists("close_button"):
            self.find_and_click("close_button")
        
        # Add your custom logic here
        # You can use:
        # - self.find_and_click(template_name) to find and click
        # - self.wait_for_image(template_name) to wait for an image
        # - self.image_exists(template_name) to check if image exists
        # - keyboard.press(key) to press keyboard keys
        # - time.sleep(seconds) to add delays
    
    def run(self):
        """Main loop for the macro"""
        print("=== Roblox Image Detection Macro ===")
        print(f"Loaded {len(self.templates)} template(s)")
        print(f"\nPress {self.config['hotkeys']['start'].upper()} to start")
        print(f"Press {self.config['hotkeys']['pause'].upper()} to pause")
        print(f"Press {self.config['hotkeys']['stop'].upper()} to stop")
        
        try:
            while True:
                if self.running and not self.paused:
                    try:
                        self.macro_logic()
                        time.sleep(self.config["detection"]["scan_interval"])
                    except Exception as e:
                        print(f"Error in macro logic: {e}")
                        time.sleep(1)
                else:
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n\nMacro interrupted by user")
        finally:
            print("Shutting down...")


def main():
    """Entry point for the macro"""
    macro = RobloxMacro()
    macro.run()


if __name__ == "__main__":
    main()
