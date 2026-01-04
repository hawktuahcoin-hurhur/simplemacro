"""
Input Recorder Macro - TinyTask-like functionality
Records and plays back keyboard and mouse inputs
"""

import json
import time
from datetime import datetime
from pathlib import Path
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController


class InputRecorder:
    """Records keyboard and mouse inputs with timestamps"""
    
    def __init__(self):
        self.events = []
        self.recording = False
        self.start_time = None
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        
        # Listeners
        self.mouse_listener = None
        self.keyboard_listener = None
    
    def start_recording(self):
        """Start recording inputs"""
        self.events = []
        self.recording = True
        self.start_time = time.time()
        print("\n🔴 Recording started...")
        
        # Start mouse listener
        self.mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll
        )
        
        # Start keyboard listener
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
    
    def stop_recording(self):
        """Stop recording inputs"""
        if not self.recording:
            return
        
        self.recording = False
        
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        print(f"⏹️  Recording stopped. Captured {len(self.events)} events.")
        return self.events
    
    def _get_timestamp(self):
        """Get timestamp relative to recording start"""
        if self.start_time:
            return time.time() - self.start_time
        return 0
    
    def _on_mouse_move(self, x, y):
        """Handle mouse move event"""
        if self.recording:
            self.events.append({
                'type': 'mouse_move',
                'timestamp': self._get_timestamp(),
                'x': x,
                'y': y
            })
    
    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click event"""
        if self.recording:
            self.events.append({
                'type': 'mouse_click',
                'timestamp': self._get_timestamp(),
                'x': x,
                'y': y,
                'button': str(button),
                'pressed': pressed
            })
    
    def _on_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll event"""
        if self.recording:
            self.events.append({
                'type': 'mouse_scroll',
                'timestamp': self._get_timestamp(),
                'x': x,
                'y': y,
                'dx': dx,
                'dy': dy
            })
    
    def _on_key_press(self, key):
        """Handle key press event"""
        if self.recording:
            try:
                key_str = key.char if hasattr(key, 'char') else str(key)
            except AttributeError:
                key_str = str(key)
            
            self.events.append({
                'type': 'key_press',
                'timestamp': self._get_timestamp(),
                'key': key_str
            })
    
    def _on_key_release(self, key):
        """Handle key release event"""
        if self.recording:
            try:
                key_str = key.char if hasattr(key, 'char') else str(key)
            except AttributeError:
                key_str = str(key)
            
            self.events.append({
                'type': 'key_release',
                'timestamp': self._get_timestamp(),
                'key': key_str
            })


class InputPlayer:
    """Plays back recorded inputs"""
    
    def __init__(self):
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.playing = False
        self.paused = False
    
    def play(self, events, speed=1.0):
        """
        Play back recorded events
        
        Args:
            events: List of recorded events
            speed: Playback speed multiplier (1.0 = normal, 2.0 = 2x speed, 0.5 = half speed)
        """
        if not events:
            print("No events to play!")
            return
        
        self.playing = True
        print(f"\n▶️  Playing back {len(events)} events at {speed}x speed...")
        
        start_time = time.time()
        
        for i, event in enumerate(events):
            if not self.playing:
                print("Playback stopped.")
                break
            
            # Wait for pauses
            while self.paused and self.playing:
                time.sleep(0.1)
            
            # Wait until the correct timestamp
            target_time = event['timestamp'] / speed
            current_time = time.time() - start_time
            wait_time = target_time - current_time
            
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Execute the event
            self._execute_event(event)
        
        self.playing = False
        print("✅ Playback complete!")
    
    def stop(self):
        """Stop playback"""
        self.playing = False
    
    def toggle_pause(self):
        """Toggle pause state"""
        self.paused = not self.paused
        if self.paused:
            print("⏸️  Playback paused")
        else:
            print("▶️  Playback resumed")
    
    def _execute_event(self, event):
        """Execute a single event"""
        event_type = event['type']
        
        try:
            if event_type == 'mouse_move':
                self.mouse_controller.position = (event['x'], event['y'])
            
            elif event_type == 'mouse_click':
                # Parse button
                button_str = event['button']
                if 'left' in button_str.lower():
                    button = Button.left
                elif 'right' in button_str.lower():
                    button = Button.right
                elif 'middle' in button_str.lower():
                    button = Button.middle
                else:
                    button = Button.left
                
                if event['pressed']:
                    self.mouse_controller.press(button)
                else:
                    self.mouse_controller.release(button)
            
            elif event_type == 'mouse_scroll':
                self.mouse_controller.scroll(event['dx'], event['dy'])
            
            elif event_type == 'key_press':
                key = self._parse_key(event['key'])
                if key:
                    self.keyboard_controller.press(key)
            
            elif event_type == 'key_release':
                key = self._parse_key(event['key'])
                if key:
                    self.keyboard_controller.release(key)
        
        except Exception as e:
            print(f"Error executing event: {e}")
    
    def _parse_key(self, key_str):
        """Parse key string back to key object"""
        # Handle special keys
        if key_str.startswith('Key.'):
            key_name = key_str.replace('Key.', '')
            try:
                return getattr(Key, key_name)
            except AttributeError:
                return None
        else:
            # Regular character
            return key_str if len(key_str) == 1 else None


class MacroRecorder:
    """Main class that manages recording and playback with hotkeys"""
    
    def __init__(self, config_path="recorder_config.json"):
        self.config = self._load_config(config_path)
        self.recorder = InputRecorder()
        self.player = InputPlayer()
        self.current_recording = None
        self.hotkey_listener = None
        self.running = True
        
        # Storage
        self.recordings_folder = Path("recordings")
        self.recordings_folder.mkdir(exist_ok=True)
    
    def _load_config(self, config_path):
        """Load or create default configuration"""
        default_config = {
            "hotkeys": {
                "record": "<ctrl>+<shift>+r",
                "stop_record": "<ctrl>+<shift>+s",
                "play": "<ctrl>+<shift>+p",
                "stop_play": "<ctrl>+<shift>+x"
            },
            "playback": {
                "default_speed": 1.0
            }
        }
        
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def start(self):
        """Start the macro recorder with hotkey listening"""
        print("\n" + "="*50)
        print("🎬 Input Recorder Macro")
        print("="*50)
        print("\nHotkeys:")
        print(f"  Record:      {self.config['hotkeys']['record']}")
        print(f"  Stop Record: {self.config['hotkeys']['stop_record']}")
        print(f"  Play:        {self.config['hotkeys']['play']}")
        print(f"  Stop Play:   {self.config['hotkeys']['stop_play']}")
        print("\nPress Ctrl+C to exit")
        print("="*50 + "\n")
        
        # Set up hotkey combinations
        hotkey_map = {
            self.config['hotkeys']['record']: self._start_recording,
            self.config['hotkeys']['stop_record']: self._stop_recording,
            self.config['hotkeys']['play']: self._play_recording,
            self.config['hotkeys']['stop_play']: self._stop_playback
        }
        
        # Start global hotkey listener
        with keyboard.GlobalHotKeys(hotkey_map) as listener:
            self.hotkey_listener = listener
            try:
                listener.join()
            except KeyboardInterrupt:
                print("\n\nExiting...")
                self.running = False
    
    def _start_recording(self):
        """Start recording callback"""
        if self.recorder.recording:
            print("Already recording!")
            return
        
        if self.player.playing:
            print("Cannot record while playing!")
            return
        
        self.recorder.start_recording()
    
    def _stop_recording(self):
        """Stop recording callback"""
        if not self.recorder.recording:
            print("Not currently recording!")
            return
        
        events = self.recorder.stop_recording()
        if events:
            self.current_recording = events
            self._save_recording(events)
    
    def _play_recording(self):
        """Play recording callback"""
        if self.player.playing:
            print("Already playing!")
            return
        
        if self.recorder.recording:
            print("Cannot play while recording!")
            return
        
        if not self.current_recording:
            print("No recording to play! Record something first or load a recording.")
            return
        
        # Play in a separate thread to not block hotkey detection
        import threading
        playback_thread = threading.Thread(
            target=self.player.play,
            args=(self.current_recording, self.config['playback']['default_speed'])
        )
        playback_thread.daemon = True
        playback_thread.start()
    
    def _stop_playback(self):
        """Stop playback callback"""
        if self.player.playing:
            self.player.stop()
        else:
            print("Not currently playing!")
    
    def _save_recording(self, events):
        """Save recording to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.recordings_folder / f"recording_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'event_count': len(events),
                'events': events
            }, f, indent=2)
        
        print(f"💾 Recording saved to: {filename}")
    
    def load_recording(self, filename):
        """Load a recording from file"""
        filepath = Path(filename)
        if not filepath.exists():
            filepath = self.recordings_folder / filename
        
        if not filepath.exists():
            print(f"Recording file not found: {filename}")
            return False
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            self.current_recording = data['events']
            print(f"📂 Loaded recording with {len(self.current_recording)} events")
            return True


def main():
    """Main entry point"""
    macro = MacroRecorder()
    macro.start()


if __name__ == "__main__":
    main()
