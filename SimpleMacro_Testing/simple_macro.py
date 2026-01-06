"""
Simple Macro - Step-based macro builder with GUI
Create macros by adding steps with hold/click actions
"""

import json
import time
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from pathlib import Path
import threading
import sv_ttk
from PIL import Image, ImageTk, ImageDraw
import mss
import cv2
import numpy as np
from pynput.keyboard import Controller as KeyboardController, Key, Listener as KeyboardListener
from pynput.mouse import Controller as MouseController, Button, Listener as MouseListener
import requests
import io
import hashlib


class SimpleMacroGUI:
    """GUI for creating and running step-based macros"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Simple Macro")
        self.root.geometry("900x750")
        self.root.minsize(700, 550)  # Minimum window size
        
        # Apply Sun Valley theme
        sv_ttk.set_theme("dark")
        
        self.steps = []
        self.playing = False
        
        # Save macros to user's Documents folder
        self.recordings_folder = Path.home() / "Documents"
        
        # Images folder for image search (in Documents)
        self.images_folder = Path.home() / "Documents" / "SimpleMacro_Images"
        self.images_folder.mkdir(exist_ok=True)
        
        # Theme settings
        self.current_theme = "dark"
        self.always_on_top = False
        
        # Playback settings
        self.playback_speed = 1.0
        self.loop_count = 1  # 0 = infinite
        self.stop_playback = False
        
            # Let the user pick any macro file from disk
            path = filedialog.askopenfilename(
                title='Load Macro',
                initialdir=str(self.recordings_folder),
                filetypes=[('Macro Files', '*.txt'), ('JSON', '*.json'), ('All Files', '*.*')]
            )
            if not path:
                return

            with open(path, 'r') as f:
                data = json.load(f)
                steps = data.get('steps', [])

            # After loading, reconcile image_search steps by image_hash (match by pixels)
            for s in steps:
                try:
                    if s.get('action') == 'image_search':
                        img_path = s.get('image_path')
                        img_hash = s.get('image_hash')

                        # If image file missing or hash missing, try to compute or find match
                        resolved = None
                        if img_path:
                            p = Path(img_path)
                            if p.exists():
                                # Ensure hash is present
                                if not img_hash:
                                    s['image_hash'] = self._compute_image_hash(p)
                                resolved = p
                        if not resolved and img_hash:
                            found = self._find_image_by_hash(img_hash)
                            if found:
                                s['image_path'] = str(found)
                                s['image_name'] = found.name
                                resolved = found

                except Exception:
                    pass

            self.steps = steps
            self._update_steps_display()
            messagebox.showinfo('Success', f"Loaded macro: {data.get('name', Path(path).stem)}")
        # Notebook for Steps / Logs
        steps_notebook = ttk.Notebook(main_frame)
        steps_notebook.pack(fill="both", expand=True, pady=(0, 10))

        steps_tab = ttk.Frame(steps_notebook)
        logs_tab = ttk.Frame(steps_notebook)
        steps_notebook.add(steps_tab, text="Steps")
        steps_notebook.add(logs_tab, text="Logs")

        # Steps listbox with scrollbar (inside Steps tab)
        list_frame = ttk.Frame(steps_tab)
        list_frame.pack(fill="both", expand=True)

        # Vertical scrollbar
        scrollbar_y = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar_y.pack(side="right", fill="y")

        # Horizontal scrollbar
        scrollbar_x = ttk.Scrollbar(list_frame, orient="horizontal")
        scrollbar_x.pack(side="bottom", fill="x")

        self.steps_listbox = tk.Listbox(
            list_frame,
            font=("Courier", 10),
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            height=15,
            selectmode=tk.EXTENDED,  # Enable multi-select with Ctrl/Shift
            exportselection=False
        )
        self.steps_listbox.pack(side="left", fill="both", expand=True)
        scrollbar_y.config(command=self.steps_listbox.yview)
        scrollbar_x.config(command=self.steps_listbox.xview)

        # Logs tab: scrolled text
        self.logs_text = scrolledtext.ScrolledText(logs_tab, height=12, state='disabled', wrap='word', font=("Consolas", 10))
        self.logs_text.pack(fill="both", expand=True, padx=6, pady=6)

        # Helper to log messages (timestamped)
        def _log(msg):
            try:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                self.logs_text.config(state='normal')
                self.logs_text.insert('end', f"[{ts}] {msg}\n")
                self.logs_text.see('end')
                self.logs_text.config(state='disabled')
            except Exception:
                pass

        self._log = _log
        
        # Button frame - Row 1 (Step management)
        button_frame1 = ttk.Frame(main_frame)
        button_frame1.pack(fill="x", pady=(10, 5))
        
        # New Step button
        self.new_step_btn = ttk.Button(
            button_frame1,
            text="➕ New Step",
            command=self._new_step_dialog
        )
        self.new_step_btn.pack(side="left", padx=5)
        
        # Delete Step button
        self.delete_step_btn = ttk.Button(
            button_frame1,
            text="🗑️ Delete Step",
            command=self._delete_step
        )
        self.delete_step_btn.pack(side="left", padx=5)
        
        # Step Options button
        self.step_options_btn = ttk.Button(
            button_frame1,
            text="⚙️ Step Options",
            command=self._edit_step_options
        )
        self.step_options_btn.pack(side="left", padx=5)
        
        # Set Loop button (for multi-select)
        self.set_loop_btn = ttk.Button(
            button_frame1,
            text="🔄 Set Loop",
            command=self._set_selected_loops
        )
        self.set_loop_btn.pack(side="left", padx=5)
        
        # Clear All button
        self.clear_btn = ttk.Button(
            button_frame1,
            text="🗑️ Clear All",
            command=self._clear_all
        )
        self.clear_btn.pack(side="left", padx=5)
        
        # Button frame - Row 2 (Recording & Settings)
        button_frame2 = ttk.Frame(main_frame)
        button_frame2.pack(fill="x", pady=(0, 10))

        # (Record button removed — use QuickRec instead)

        # Quick recorder button (start/stop toggle)
        self.quickrec_btn = ttk.Button(
            button_frame2,
            text="🎥 QuickRec",
            command=self._toggle_quickrec
        )
        self.quickrec_btn.pack(side="left", padx=5)
        
        # Image Search button
        self.image_search_btn = ttk.Button(
            button_frame2,
            text="🔍 Image Search",
            command=self._add_image_search_step
        )
        self.image_search_btn.pack(side="left", padx=5)
        
        # Global Settings button
        self.settings_btn = ttk.Button(
            button_frame2,
            text="⚙️ Global Settings",
            command=self._open_settings
        )
        self.settings_btn.pack(side="left", padx=5)

        # Guide button - opens comprehensive help
        self.guide_btn = ttk.Button(
            button_frame2,
            text="📘 Guide",
            command=self._open_guide
        )
        self.guide_btn.pack(side="left", padx=5)
        
        # Action buttons frame
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=10)
        
        # Save button
        self.save_btn = ttk.Button(
            action_frame,
            text="💾 Save",
            command=self._save_macro
        )
        self.save_btn.pack(side="left", padx=5, expand=True, fill="x")
        
        # Play/Stop button (with hotkey - toggles)
        self.play_btn = ttk.Button(
            action_frame,
            text=f"▶️ Play ({self.play_hotkey})",
            command=self._toggle_play
        )
        self.play_btn.pack(side="left", padx=5, expand=True, fill="x")
        
        # Load button
        self.load_btn = ttk.Button(
            action_frame,
            text="📂 Load",
            command=self._load_macro
        )
        self.load_btn.pack(side="left", padx=5, expand=True, fill="x")
        
        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side="bottom", fill="x")
        
        self.status_label = ttk.Label(
            status_frame,
            text="Ready",
            relief="sunken",
            anchor="w",
            padding=(10, 5)
        )
        self.status_label.pack(fill="x")
    
    def _new_step_dialog(self):
        """Open dialog to create a new step"""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Step")
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create scrollable container
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding=20)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        main_frame = scrollable_frame
        
        # Step name (optional)
        ttk.Label(main_frame, text="Step Name (optional):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=name_var, font=("Arial", 10), width=30)
        name_entry.pack(anchor="w", pady=(0, 15))
        
        # Action type selection
        ttk.Label(main_frame, text="Action Type:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        action_var = tk.StringVar(value="click")
        
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(anchor="w", pady=(0, 15))
        
        ttk.Radiobutton(action_frame, text="Click", variable=action_var, value="click").pack(side="left", padx=10)
        ttk.Radiobutton(action_frame, text="Hold", variable=action_var, value="hold").pack(side="left", padx=10)
        ttk.Radiobutton(action_frame, text="Type", variable=action_var, value="type").pack(side="left", padx=10)
        ttk.Radiobutton(action_frame, text="Scroll", variable=action_var, value="scroll").pack(side="left", padx=10)
        
        # Key selection (for click/hold)
        key_section = ttk.Frame(main_frame)
        key_label = ttk.Label(key_section, text="Key:", font=("Arial", 11, "bold"))
        key_label.pack(anchor="w", pady=(0, 5))
        
        key_var = tk.StringVar()
        key_entry = ttk.Entry(key_section, textvariable=key_var, font=("Arial", 10), width=30)
        key_entry.pack(anchor="w", pady=(0, 5))
        
        key_hint = ttk.Label(key_section, text="(e.g., 'a', 'enter', 'space', 'shift', 'ctrl', 'left_click', 'right_click')", 
                 font=("Arial", 8))
        key_hint.pack(anchor="w", pady=(0, 15))
        
        # Text input section (for type action)
        text_section = ttk.Frame(main_frame)
        text_label = ttk.Label(text_section, text="Text to Type:", font=("Arial", 11, "bold"))
        text_label.pack(anchor="w", pady=(0, 5))
        
        text_var = tk.StringVar()
        text_entry = ttk.Entry(text_section, textvariable=text_var, font=("Arial", 10), width=40)
        text_entry.pack(anchor="w", pady=(0, 5))
        
        text_hint = ttk.Label(text_section, text="(Enter the text/characters you want to type)", 
                 font=("Arial", 8))
        text_hint.pack(anchor="w", pady=(0, 15))
        
        # Scroll input section (for scroll action)
        scroll_section = ttk.Frame(main_frame)
        scroll_label = ttk.Label(scroll_section, text="Scroll Amount:", font=("Arial", 11, "bold"))
        scroll_label.pack(anchor="w", pady=(0, 5))
        
        scroll_var = tk.StringVar(value="3")
        scroll_entry = ttk.Entry(scroll_section, textvariable=scroll_var, font=("Arial", 10), width=10)
        scroll_entry.pack(anchor="w", pady=(0, 5))
        
        scroll_hint = ttk.Label(scroll_section, text="(Positive = scroll up, Negative = scroll down. e.g., 3 or -5)", 
                 font=("Arial", 8))
        scroll_hint.pack(anchor="w", pady=(0, 15))
        
        # Coordinates section (for mouse clicks)
        coord_container = ttk.Frame(main_frame)
        
        coord_label = ttk.Label(coord_container, text="Coordinates (X, Y):", font=("Arial", 11, "bold"))
        
        x_var = tk.StringVar(value="0")
        y_var = tk.StringVar(value="0")
        
        coord_entry_frame = ttk.Frame(coord_container)
        x_label = ttk.Label(coord_entry_frame, text="X:", font=("Arial", 10))
        x_entry = ttk.Entry(coord_entry_frame, textvariable=x_var, font=("Arial", 10), width=8)
        y_label = ttk.Label(coord_entry_frame, text="Y:", font=("Arial", 10))
        y_entry = ttk.Entry(coord_entry_frame, textvariable=y_var, font=("Arial", 10), width=8)
        
        # Select Coordinates button
        select_coord_btn = ttk.Button(
            coord_container,
            text="📍 Select Coordinates",
            command=lambda: self._open_coordinate_picker(x_var, y_var, dialog)
        )
        
        # Amount/Duration section
        amount_container = ttk.Frame(main_frame)
        amount_label = ttk.Label(amount_container, text="Amount (clicks):", font=("Arial", 11, "bold"))
        
        amount_var = tk.StringVar(value="1")
        amount_entry = ttk.Entry(amount_container, textvariable=amount_var, font=("Arial", 10), width=10)
        
        def toggle_ui(*args):
            """Toggle UI based on action type and key input"""
            action = action_var.get()
            key = key_var.get().lower()
            
            # Show/hide sections based on action type
            if action == "type":
                key_section.pack_forget()
                text_section.pack(anchor="w", fill="x", pady=(0, 10))
                scroll_section.pack_forget()
                coord_container.pack_forget()
                amount_container.pack_forget()
            elif action == "scroll":
                key_section.pack_forget()
                text_section.pack_forget()
                scroll_section.pack(anchor="w", fill="x", pady=(0, 10))
                # Show coordinates for scroll position (optional)
                coord_container.pack(anchor="w", fill="x", pady=(0, 10))
                coord_label.pack(anchor="w", pady=(0, 5))
                coord_entry_frame.pack(anchor="w", pady=(0, 5))
                x_label.pack(side="left")
                x_entry.pack(side="left", padx=(5, 10))
                y_label.pack(side="left")
                y_entry.pack(side="left", padx=5)
                select_coord_btn.pack(anchor="w", pady=(5, 10))
                amount_container.pack_forget()
            else:
                text_section.pack_forget()
                scroll_section.pack_forget()
                key_section.pack(anchor="w", fill="x", pady=(0, 10))
                
                # Show coordinates if mouse click
                if 'click' in key:
                    coord_container.pack(anchor="w", fill="x", pady=(0, 10))
                    coord_label.pack(anchor="w", pady=(0, 5))
                    coord_entry_frame.pack(anchor="w", pady=(0, 5))
                    x_label.pack(side="left")
                    x_entry.pack(side="left", padx=(5, 10))
                    y_label.pack(side="left")
                    y_entry.pack(side="left", padx=5)
                    select_coord_btn.pack(anchor="w", pady=(5, 10))
                else:
                    coord_container.pack_forget()
                    coord_label.pack_forget()
                    coord_entry_frame.pack_forget()
                    x_label.pack_forget()
                    x_entry.pack_forget()
                    y_label.pack_forget()
                    y_entry.pack_forget()
                    select_coord_btn.pack_forget()
                
                # Show amount/duration
                amount_container.pack(anchor="w", fill="x", pady=(0, 10))
                amount_label.pack(anchor="w", pady=(0, 5))
                amount_entry.pack(anchor="w", pady=(0, 5))
                
                # Update label based on action type
                if action == "hold":
                    amount_label.config(text="Duration (seconds):")
                    if amount_var.get() == "1":
                        amount_var.set("1.0")
                else:
                    amount_label.config(text="Amount (clicks):")
                    if amount_var.get() == "1.0":
                        amount_var.set("1")
        
        key_var.trace('w', toggle_ui)
        action_var.trace('w', toggle_ui)
        
        # Initialize UI state
        toggle_ui()
        
        # Delay
        ttk.Label(main_frame, text="Delay After (seconds):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        delay_var = tk.StringVar(value="0.5")
        delay_entry = ttk.Entry(main_frame, textvariable=delay_var, font=("Arial", 10), width=10)
        delay_entry.pack(anchor="w", pady=(0, 20))
        
        # Buttons
        def add_step():
            action = action_var.get()
            
            # Handle type action
            if action == "type":
                typed_text = text_var.get()
                if not typed_text:
                    messagebox.showerror("Error", "Please enter text to type!")
                    return
                
                try:
                    delay_value = float(delay_var.get())
                except ValueError:
                    messagebox.showerror("Error", "Delay must be a number!")
                    return
                
                step = {
                    'action': 'type',
                    'text': typed_text,
                    'delay': delay_value,
                    'name': name_var.get().strip()
                }
            elif action == "scroll":
                try:
                    scroll_amount = int(scroll_var.get())
                    delay_value = float(delay_var.get())
                except ValueError:
                    messagebox.showerror("Error", "Scroll amount must be an integer and delay must be a number!")
                    return
                
                step = {
                    'action': 'scroll',
                    'scroll_amount': scroll_amount,
                    'delay': delay_value,
                    'name': name_var.get().strip()
                }
                
                # Add coordinates if specified (scroll at position)
                try:
                    x_val = int(x_var.get())
                    y_val = int(y_var.get())
                    if x_val != 0 or y_val != 0:
                        step['x'] = x_val
                        step['y'] = y_val
                except ValueError:
                    pass  # No coordinates, scroll at current position
            else:
                # Handle click/hold action
                key = key_var.get().strip()
                if not key:
                    messagebox.showerror("Error", "Please enter a key!")
                    return
                
                try:
                    amount_value = float(amount_var.get())
                    delay_value = float(delay_var.get())
                except ValueError:
                    messagebox.showerror("Error", "Amount and delay must be numbers!")
                    return
                
                step = {
                    'action': action,
                    'key': key,
                    'amount': amount_value,
                    'delay': delay_value,
                    'name': name_var.get().strip()
                }
                
                # Add coordinates if it's a mouse click
                if 'click' in key.lower():
                    try:
                        step['x'] = int(x_var.get())
                        step['y'] = int(y_var.get())
                    except ValueError:
                        messagebox.showerror("Error", "Coordinates must be numbers!")
                        return
            
            # Unbind mousewheel when closing
            canvas.unbind_all("<MouseWheel>")
            
            self.steps.append(step)
            self._update_steps_display()
            dialog.destroy()
        
        def cancel():
            canvas.unbind_all("<MouseWheel>")
            dialog.destroy()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(button_frame, text="Add Step", command=add_step).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side="left", padx=5)
    
    def _open_coordinate_picker(self, x_var, y_var, parent_dialog):
        """Open a screenshot for coordinate picking with drawing"""
        # Release the grab from parent dialog so picker can receive input
        parent_dialog.grab_release()
        
        # Hide the parent dialog temporarily
        parent_dialog.withdraw()
        self.root.withdraw()
        time.sleep(0.3)  # Wait for windows to hide
        
        # Take screenshot and store monitor offset for coordinate conversion
        with mss.mss() as sct:
            # Use monitor[1] for primary monitor (monitor[0] is the combined virtual screen)
            # This gives us proper coordinate mapping
            monitor = sct.monitors[1]  # Primary monitor
            self.monitor_offset_x = monitor['left']
            self.monitor_offset_y = monitor['top']
            screenshot = sct.grab(monitor)
            img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        
        # Create fullscreen picker window
        picker = tk.Toplevel()
        picker.attributes('-fullscreen', True)
        picker.attributes('-topmost', True)
        picker.title("Select Coordinates - Click to place marker, Draw to annotate")
        
        # Store drawing state
        self.drawing = False
        self.draw_start = None
        self.marked_coords = None
        self.draw_items = []
        
        # Create canvas with screenshot
        img_tk = ImageTk.PhotoImage(img)
        canvas = tk.Canvas(picker, width=img.width, height=img.height, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_image(0, 0, anchor="nw", image=img_tk)
        canvas.image = img_tk  # Keep reference
        
        # Info label
        info_frame = tk.Frame(picker, bg="#2c3e50")
        info_frame.place(x=10, y=10)
        
        info_label = tk.Label(
            info_frame,
            text="🎯 Left-click: Set coordinates  |  🖊️ Right-click + Drag: Draw  |  Enter: Confirm  |  Esc: Cancel",
            font=("Arial", 12, "bold"),
            bg="#2c3e50",
            fg="white",
            padx=10,
            pady=5
        )
        info_label.pack()
        
        # Coordinates display
        coord_display = tk.Label(
            picker,
            text="Coordinates: (-, -)",
            font=("Arial", 14, "bold"),
            bg="#27ae60",
            fg="white",
            padx=15,
            pady=8
        )
        coord_display.place(x=10, y=60)
        
        # Crosshair lines
        h_line = None
        v_line = None
        marker = None
        
        def on_mouse_move(event):
            nonlocal h_line, v_line
            # Update crosshair
            if h_line:
                canvas.delete(h_line)
            if v_line:
                canvas.delete(v_line)
            
            h_line = canvas.create_line(0, event.y, img.width, event.y, fill="#3498db", width=1, dash=(4, 4))
            v_line = canvas.create_line(event.x, 0, event.x, img.height, fill="#3498db", width=1, dash=(4, 4))
            
            # Calculate actual screen coordinates (canvas position + monitor offset)
            screen_x = event.x + self.monitor_offset_x
            screen_y = event.y + self.monitor_offset_y
            
            # Update live coordinates - show both canvas and screen coords
            coord_display.config(text=f"Screen: ({screen_x}, {screen_y})")
        
        def on_left_click(event):
            nonlocal marker
            # Calculate actual screen coordinates
            screen_x = event.x + self.monitor_offset_x
            screen_y = event.y + self.monitor_offset_y
            
            # Set screen coordinates (not canvas coordinates)
            self.marked_coords = (screen_x, screen_y)
            coord_display.config(text=f"✓ Selected: ({screen_x}, {screen_y})")
            
            # Draw marker at canvas position
            if marker:
                for item in marker:
                    canvas.delete(item)
            
            size = 15
            marker = [
                canvas.create_oval(event.x-size, event.y-size, event.x+size, event.y+size, 
                                  outline="#e74c3c", width=3),
                canvas.create_line(event.x-size-5, event.y, event.x+size+5, event.y, 
                                  fill="#e74c3c", width=2),
                canvas.create_line(event.x, event.y-size-5, event.x, event.y+size+5, 
                                  fill="#e74c3c", width=2)
            ]
        
        def on_right_press(event):
            self.drawing = True
            self.draw_start = (event.x, event.y)
        
        def on_right_drag(event):
            if self.drawing and self.draw_start:
                line = canvas.create_line(
                    self.draw_start[0], self.draw_start[1],
                    event.x, event.y,
                    fill="#f39c12", width=3, capstyle="round"
                )
                self.draw_items.append(line)
                self.draw_start = (event.x, event.y)
        
        def on_right_release(event):
            self.drawing = False
            self.draw_start = None
        
        def confirm(event=None):
            if self.marked_coords:
                x_var.set(str(self.marked_coords[0]))
                y_var.set(str(self.marked_coords[1]))
            picker.destroy()
            self.root.deiconify()
            parent_dialog.deiconify()
            parent_dialog.grab_set()  # Restore grab
        
        def cancel(event=None):
            picker.destroy()
            self.root.deiconify()
            parent_dialog.deiconify()
            parent_dialog.grab_set()  # Restore grab
        
        def clear_drawings(event=None):
            for item in self.draw_items:
                canvas.delete(item)
            self.draw_items = []
        
        # Bind mouse events to canvas
        canvas.bind("<Motion>", on_mouse_move)
        canvas.bind("<Button-1>", on_left_click)
        canvas.bind("<Button-3>", on_right_press)
        canvas.bind("<B3-Motion>", on_right_drag)
        canvas.bind("<ButtonRelease-3>", on_right_release)
        
        # Bind keyboard events globally using bind_all for reliable capture
        picker.bind_all("<Return>", confirm)
        picker.bind_all("<Escape>", cancel)
        picker.bind_all("<c>", clear_drawings)
        picker.bind_all("<C>", clear_drawings)
        
        # Make canvas focusable and give it focus
        canvas.config(takefocus=True)
        canvas.focus_set()
        
        # Also bind to canvas directly as backup
        canvas.bind("<Return>", confirm)
        canvas.bind("<Escape>", cancel)
        canvas.bind("<c>", clear_drawings)
        canvas.bind("<C>", clear_drawings)
        
        # Buttons at bottom
        btn_frame = tk.Frame(picker, bg="#34495e")
        btn_frame.place(relx=0.5, rely=0.95, anchor="center")
        
        ttk.Button(btn_frame, text="✓ Confirm (Enter)", command=confirm).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="✗ Cancel (Esc)", command=cancel).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🧹 Clear Drawings (C)", command=clear_drawings).pack(side="left", padx=5)
        
        # Ensure picker window has focus
        picker.focus_force()
        picker.lift()
        picker.after(100, lambda: canvas.focus_set())
    
    def _update_steps_display(self):
        """Update the steps listbox display"""
        self.steps_listbox.delete(0, tk.END)
        
        for i, step in enumerate(self.steps, 1):
            coord_text = ""
            if 'x' in step and 'y' in step:
                coord_text = f" at ({step['x']}, {step['y']})"
            
            # Build step options text
            step_opts = ""
            if step.get('step_speed', 1.0) != 1.0:
                step_opts += f" @{step['step_speed']:.1f}x"
            step_loop = step.get('step_loop', 1)
            if step_loop == 0:
                step_opts += " 🔁∞"
            elif step_loop == 1:
                step_opts += " 🔂1"  # Run once only indicator
            elif step_loop > 1:
                step_opts += f" 🔁{step_loop}"
            
            # Get step name if exists
            step_name = step.get('name', '')
            name_prefix = f"[{step_name}] " if step_name else ""
            
            if step['action'] == 'image_search':
                click_text = ""
                if step.get('click_image'):
                    click_mode = step.get('click_mode', 'offset')
                    if click_mode == 'absolute' and 'abs_x' in step:
                        click_text = f" -> Click at ({step['abs_x']}, {step['abs_y']})"
                    else:
                        offset_x = step.get('offset_x', 0)
                        offset_y = step.get('offset_y', 0)
                        click_text = f" -> Click"
                        if offset_x != 0 or offset_y != 0:
                            click_text += f" (+{offset_x}, +{offset_y})"
                timeout = step.get('search_timeout', 30)
                timeout_text = f" ⏱{timeout}s" if timeout > 0 else " ⏱∞"
                text = f"{i}. {name_prefix}WAIT Image '{step['image_name']}'{timeout_text}{click_text}{step_opts}  [Delay: {step['delay']}s]"
            elif step['action'] == 'type':
                # Truncate long text for display
                typed_text = step.get('text', '')
                display_text = typed_text[:30] + "..." if len(typed_text) > 30 else typed_text
                text = f"{i}. {name_prefix}Type \"{display_text}\"{step_opts}  [Delay: {step['delay']}s]"
            elif step['action'] == 'scroll':
                scroll_amount = step.get('scroll_amount', 0)
                direction = "up" if scroll_amount > 0 else "down"
                text = f"{i}. {name_prefix}Scroll {direction} {abs(scroll_amount)}{coord_text}{step_opts}  [Delay: {step['delay']}s]"
            elif step['action'] == 'click':
                text = f"{i}. {name_prefix}Click '{step['key']}'{coord_text} x{int(step['amount'])} times{step_opts}  [Delay: {step['delay']}s]"
            else:
                text = f"{i}. {name_prefix}Hold '{step['key']}'{coord_text} for {step['amount']}s{step_opts}  [Delay: {step['delay']}s]"
            
            self.steps_listbox.insert(tk.END, text)
        
        self.status_label.config(text=f"Total steps: {len(self.steps)}")
    
    def _delete_step(self):
        """Delete selected step"""
        selection = self.steps_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a step to delete!")
            return
        
        index = selection[0]
        del self.steps[index]
        self._update_steps_display()
    
    def _set_selected_loops(self):
        """Set loop count for all selected steps (supports multi-select)"""
        selection = self.steps_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select one or more steps!")
            return

        # Capture selection indices now to avoid focus changes clearing selection
        selected_indices = [int(x) for x in selection]

        dialog = tk.Toplevel(self.root)
        dialog.title("Set Loop Count")
        dialog.geometry("380x220")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(dialog, padding=25)
        frame.pack(fill="both", expand=True)
        
        count_text = f"Selected: {len(selected_indices)} step(s)"
        ttk.Label(frame, text=count_text, font=("Arial", 11, "bold")).pack(pady=(0, 20))
        
        ttk.Label(frame, text="Set Loop Count:", font=("Arial", 11)).pack(anchor="w")
        ttk.Label(frame, text="0 = Infinite, 1 = Run once only (per playback)", 
                 font=("Arial", 9)).pack(anchor="w", pady=(0, 5))
        
        loop_var = tk.IntVar(value=1)
        loop_spinner = ttk.Spinbox(frame, from_=0, to=1000, textvariable=loop_var, width=10)
        loop_spinner.pack(anchor="w", pady=5)
        
        def apply_loop():
            new_loop = loop_var.get()
            for idx in selected_indices:
                # guard against index out of range in case steps changed
                if 0 <= idx < len(self.steps):
                    self.steps[idx]['step_loop'] = new_loop
            self._update_steps_display()
            dialog.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=15)
        
        ttk.Button(btn_frame, text="Apply", command=apply_loop).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

    def _edit_step_options(self):
        """Edit all properties for a selected step"""
        selection = self.steps_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a step to edit!")
            return
        
        index = selection[0]
        step = self.steps[index]
        action = step.get('action', 'click')
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Step {index + 1}")
        dialog.geometry("500x650")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create scrollable frame
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding=20)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = scrollable_frame
        
        ttk.Label(frame, text=f"✏️ Edit Step {index + 1}", font=("Arial", 14, "bold")).pack(pady=(0, 10))
        ttk.Label(frame, text=f"Action Type: {action.upper()}", font=("Arial", 10, "italic")).pack(pady=(0, 15))
        
        # Step name
        name_frame = ttk.Frame(frame)
        name_frame.pack(fill="x", pady=5)
        ttk.Label(name_frame, text="Step Name:", font=("Arial", 10, "bold")).pack(anchor="w")
        name_var = tk.StringVar(value=step.get('name', ''))
        ttk.Entry(name_frame, textvariable=name_var, width=30).pack(anchor="w", pady=(2, 0))
        
        # Action-specific fields
        key_var = tk.StringVar(value=step.get('key', ''))
        text_var = tk.StringVar(value=step.get('text', ''))
        scroll_var = tk.StringVar(value=str(step.get('scroll_amount', 0)))
        x_var = tk.StringVar(value=str(step.get('x', 0)))
        y_var = tk.StringVar(value=str(step.get('y', 0)))
        amount_var = tk.StringVar(value=str(step.get('amount', 1)))
        delay_var = tk.StringVar(value=str(step.get('delay', 0.5)))
        
        # Show fields based on action type
        if action == 'type':
            # Text field
            text_frame = ttk.LabelFrame(frame, text="Text to Type", padding=10)
            text_frame.pack(fill="x", pady=10)
            ttk.Entry(text_frame, textvariable=text_var, width=40).pack(fill="x")
        
        elif action == 'scroll':
            # Scroll amount
            scroll_frame = ttk.LabelFrame(frame, text="Scroll Settings", padding=10)
            scroll_frame.pack(fill="x", pady=10)
            
            ttk.Label(scroll_frame, text="Scroll Amount (+ = up, - = down):").pack(anchor="w")
            ttk.Entry(scroll_frame, textvariable=scroll_var, width=10).pack(anchor="w", pady=5)
            
            # Coordinates
            coord_row = ttk.Frame(scroll_frame)
            coord_row.pack(fill="x", pady=5)
            ttk.Label(coord_row, text="X:").pack(side="left")
            ttk.Entry(coord_row, textvariable=x_var, width=8).pack(side="left", padx=5)
            ttk.Label(coord_row, text="Y:").pack(side="left", padx=(10, 0))
            ttk.Entry(coord_row, textvariable=y_var, width=8).pack(side="left", padx=5)
            
            ttk.Button(scroll_frame, text="📍 Select Coordinates",
                      command=lambda: self._open_coordinate_picker(x_var, y_var, dialog)).pack(anchor="w", pady=5)
        
        elif action == 'image_search':
            # Image search settings
            img_frame = ttk.LabelFrame(frame, text="Image Search Settings", padding=10)
            img_frame.pack(fill="x", pady=10)

            ttk.Label(img_frame, text=f"Image: {step.get('image_name', 'Unknown')}", font=("Arial", 10)).pack(anchor="w")

            # Confidence
            conf_var = tk.DoubleVar(value=step.get('confidence', 0.8))
            conf_row = ttk.Frame(img_frame)
            conf_row.pack(fill="x", pady=5)
            ttk.Label(conf_row, text="Confidence:").pack(side="left")
            conf_entry_var = tk.StringVar(value=f"{conf_var.get():.2f}")
            ttk.Entry(conf_row, textvariable=conf_entry_var, width=8).pack(side="left", padx=5)

            # Search timeout
            timeout_row = ttk.Frame(img_frame)
            timeout_row.pack(fill="x", pady=5)
            ttk.Label(timeout_row, text="Search Timeout (sec):").pack(side="left")
            timeout_edit_var = tk.StringVar(value=str(step.get('search_timeout', 30)))
            ttk.Entry(timeout_row, textvariable=timeout_edit_var, width=8).pack(side="left", padx=5)
            ttk.Label(timeout_row, text="(0 = wait forever)", font=("Arial", 8)).pack(side="left")

            # On-timeout behavior
            on_timeout_var = tk.StringVar(value=step.get('on_timeout', 'move_on'))
            ttk.Label(img_frame, text="On timeout:", font=("Arial", 10)).pack(anchor="w", pady=(8,0))
            on_to_frame = ttk.Frame(img_frame)
            on_to_frame.pack(fill="x", pady=2)
            ttk.Radiobutton(on_to_frame, text="Move on to next step", variable=on_timeout_var, value="move_on").pack(anchor="w")
            ttk.Radiobutton(on_to_frame, text="Retry search after timeout", variable=on_timeout_var, value="retry").pack(anchor="w")

            # Click settings
            click_var = tk.BooleanVar(value=step.get('click_image', False))
            ttk.Checkbutton(img_frame, text="Click when found", variable=click_var).pack(anchor="w")

            # Click count
            click_count_row = ttk.Frame(img_frame)
            click_count_row.pack(fill="x", pady=5)
            ttk.Label(click_count_row, text="Click Count:").pack(side="left")
            click_count_var = tk.StringVar(value=str(step.get('click_count', 1)))
            ttk.Entry(click_count_row, textvariable=click_count_var, width=8).pack(side="left", padx=5)
            
        elif action in ('click', 'hold'):
            # Key field
            key_frame = ttk.LabelFrame(frame, text="Key/Button", padding=10)
            key_frame.pack(fill="x", pady=10)
            ttk.Entry(key_frame, textvariable=key_var, width=30).pack(anchor="w")
            ttk.Label(key_frame, text="(e.g., 'a', 'enter', 'left_click', 'right_click')", 
                     font=("Arial", 8)).pack(anchor="w")
            
            # Coordinates (for mouse)
            coord_frame = ttk.LabelFrame(frame, text="Coordinates (for mouse)", padding=10)
            coord_frame.pack(fill="x", pady=10)
            
            coord_row = ttk.Frame(coord_frame)
            coord_row.pack(fill="x")
            ttk.Label(coord_row, text="X:").pack(side="left")
            ttk.Entry(coord_row, textvariable=x_var, width=8).pack(side="left", padx=5)
            ttk.Label(coord_row, text="Y:").pack(side="left", padx=(10, 0))
            ttk.Entry(coord_row, textvariable=y_var, width=8).pack(side="left", padx=5)
            
            ttk.Button(coord_frame, text="📍 Select Coordinates",
                      command=lambda: self._open_coordinate_picker(x_var, y_var, dialog)).pack(anchor="w", pady=5)
            
            # Amount/Duration
            amount_frame = ttk.LabelFrame(frame, text="Amount/Duration", padding=10)
            amount_frame.pack(fill="x", pady=10)
            
            if action == 'click':
                ttk.Label(amount_frame, text="Click Count:").pack(anchor="w")
            else:
                ttk.Label(amount_frame, text="Hold Duration (seconds):").pack(anchor="w")
            ttk.Entry(amount_frame, textvariable=amount_var, width=10).pack(anchor="w", pady=5)
        
        # Delay (for all actions)
        delay_frame = ttk.LabelFrame(frame, text="Delay After Step", padding=10)
        delay_frame.pack(fill="x", pady=10)
        ttk.Label(delay_frame, text="Delay (seconds):").pack(anchor="w")
        ttk.Entry(delay_frame, textvariable=delay_var, width=10).pack(anchor="w", pady=5)
        
        # Step-specific speed multiplier
        speed_frame = ttk.LabelFrame(frame, text="Step Speed Multiplier", padding=10)
        speed_frame.pack(fill="x", pady=10)
        
        step_speed_var = tk.DoubleVar(value=step.get('step_speed', 1.0))
        speed_label = ttk.Label(speed_frame, text=f"{step_speed_var.get():.1f}x", font=("Arial", 10, "bold"))
        speed_label.pack(anchor="e")
        
        def update_speed_label(val):
            speed_label.config(text=f"{float(val):.1f}x")
        
        speed_slider = ttk.Scale(speed_frame, from_=0.1, to=50.0, variable=step_speed_var,
                                orient="horizontal", command=update_speed_label)
        speed_slider.pack(fill="x", pady=5)
        
        # Step-specific loop count
        loop_frame = ttk.LabelFrame(frame, text="Step Loop Count", padding=10)
        loop_frame.pack(fill="x", pady=10)
        
        loop_row = ttk.Frame(loop_frame)
        loop_row.pack(fill="x")
        step_loop_var = tk.IntVar(value=step.get('step_loop', 1))
        ttk.Label(loop_row, text="Repeat:").pack(side="left")
        ttk.Spinbox(loop_row, from_=0, to=1000, textvariable=step_loop_var, width=8).pack(side="left", padx=5)
        ttk.Label(loop_row, text="times").pack(side="left")
        
        ttk.Label(loop_frame, text="0 = Infinite | 1 = Run once only (per playback)", 
                 font=("Arial", 8)).pack(anchor="w", pady=(5, 0))
        
        # Save button
        def save_step():
            try:
                # Update common fields
                self.steps[index]['name'] = name_var.get().strip()
                self.steps[index]['delay'] = float(delay_var.get())
                self.steps[index]['step_speed'] = step_speed_var.get()
                self.steps[index]['step_loop'] = step_loop_var.get()
                
                # Update action-specific fields
                if action == 'type':
                    self.steps[index]['text'] = text_var.get()
                elif action == 'scroll':
                    self.steps[index]['scroll_amount'] = int(scroll_var.get())
                    self.steps[index]['x'] = int(x_var.get())
                    self.steps[index]['y'] = int(y_var.get())
                elif action == 'image_search':
                    self.steps[index]['click_image'] = click_var.get()
                    self.steps[index]['confidence'] = float(conf_entry_var.get())
                    self.steps[index]['search_timeout'] = float(timeout_edit_var.get())
                    self.steps[index]['on_timeout'] = on_timeout_var.get()
                    try:
                        self.steps[index]['click_count'] = int(click_count_var.get())
                    except Exception:
                        self.steps[index]['click_count'] = 1
                elif action in ('click', 'hold'):
                    self.steps[index]['key'] = key_var.get().strip()
                    self.steps[index]['amount'] = float(amount_var.get())
                    if 'click' in key_var.get().lower():
                        self.steps[index]['x'] = int(x_var.get())
                        self.steps[index]['y'] = int(y_var.get())
                
                canvas.unbind_all("<MouseWheel>")
                self._update_steps_display()
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid value: {e}")
        
        def cancel():
            canvas.unbind_all("<MouseWheel>")
            dialog.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="💾 Save Changes", command=save_step).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side="left", padx=5)
    
    def _clear_all(self):
        """Clear all steps"""
        if self.steps and messagebox.askyesno("Confirm", "Clear all steps?"):
            self.steps = []
            self._update_steps_display()
    
    def _stop_macro(self):
        """Stop the currently playing macro"""
        if self.playing:
            self.stop_playback = True
            self.status_label.config(text="⏹️ Stopping...")
        else:
            messagebox.showinfo("Info", "No macro is currently playing.")
    
    def _open_settings(self):
        """Open settings dialog for loop count, playback speed, and theme"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Global Settings")
        dialog.geometry("450x700")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create scrollable frame
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding=20)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = scrollable_frame
        
        ttk.Label(frame, text="⚙️ Global Settings", font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        # Hotkey settings
        hotkey_frame = ttk.LabelFrame(frame, text="⌨️ Hotkeys", padding=10)
        hotkey_frame.pack(fill="x", pady=10)
        
        play_row = ttk.Frame(hotkey_frame)
        play_row.pack(fill="x", pady=5)
        ttk.Label(play_row, text="Play Hotkey:", font=("Arial", 10)).pack(side="left")
        play_hotkey_var = tk.StringVar(value=self.play_hotkey)
        ttk.Entry(play_row, textvariable=play_hotkey_var, width=10).pack(side="right")
        
        record_row = ttk.Frame(hotkey_frame)
        record_row.pack(fill="x", pady=5)
        ttk.Label(record_row, text="Record Hotkey:", font=("Arial", 10)).pack(side="left")
        record_hotkey_var = tk.StringVar(value=self.record_hotkey)
        ttk.Entry(record_row, textvariable=record_hotkey_var, width=10).pack(side="right")
        
        ttk.Label(hotkey_frame, text="Press twice to stop. Examples: F6, F7, F8, etc.", 
                 font=("Arial", 8)).pack(anchor="w", pady=(5, 0))
        
        # Always on top option
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill="x", pady=10)
        
        always_on_top_var = tk.BooleanVar(value=self.always_on_top)
        
        def toggle_always_on_top():
            self.always_on_top = always_on_top_var.get()
            self.root.attributes('-topmost', self.always_on_top)
        
        ttk.Checkbutton(top_frame, text="📌 Always on Top", variable=always_on_top_var,
                       command=toggle_always_on_top).pack(anchor="w")
        
        # Loop count
        loop_frame = ttk.Frame(frame)
        loop_frame.pack(fill="x", pady=10)
        
        ttk.Label(loop_frame, text="Loop Count:", font=("Arial", 11)).pack(side="left")
        ttk.Label(loop_frame, text="(0 = infinite)", font=("Arial", 9)).pack(side="left", padx=(5, 10))
        
        loop_var = tk.IntVar(value=self.loop_count)
        loop_spinner = ttk.Spinbox(loop_frame, from_=0, to=1000, textvariable=loop_var, width=10)
        loop_spinner.pack(side="right")
        
        # Playback speed
        speed_frame = ttk.Frame(frame)
        speed_frame.pack(fill="x", pady=10)
        
        ttk.Label(speed_frame, text="Playback Speed:", font=("Arial", 11)).pack(anchor="w")
        
        speed_var = tk.DoubleVar(value=self.playback_speed)
        speed_label = ttk.Label(speed_frame, text=f"{self.playback_speed:.1f}x", font=("Arial", 10, "bold"))
        speed_label.pack(anchor="e")
        
        def update_speed_label(val):
            speed_label.config(text=f"{float(val):.1f}x")
        
        speed_slider = ttk.Scale(speed_frame, from_=0.1, to=50.0, variable=speed_var, 
                                 orient="horizontal", command=update_speed_label)
        speed_slider.pack(fill="x", pady=5)
        
        # Speed presets
        preset_frame = ttk.Frame(frame)
        preset_frame.pack(fill="x", pady=5)
        
        ttk.Label(preset_frame, text="Presets:", font=("Arial", 9)).pack(side="left")
        for speed in [1.0, 5.0, 10.0, 25.0, 50.0]:
            ttk.Button(preset_frame, text=f"{int(speed) if speed == int(speed) else speed}x", width=5,
                      command=lambda s=speed: [speed_var.set(s), update_speed_label(s)]).pack(side="left", padx=2)
        
        # Theme selection
        theme_frame = ttk.LabelFrame(frame, text="🎨 Theme", padding=10)
        theme_frame.pack(fill="x", pady=15)
        
        theme_var = tk.StringVar(value=self.current_theme)
        
        themes = [
            ("dark", "🌙 Dark (Default)"),
            ("light", "☀️ Light"),
            ("ocean", "🌊 Ocean Blue"),
            ("forest", "🌲 Forest Green"),
            ("sunset", "🌅 Sunset Orange"),
            ("cyberpunk", "💜 Cyberpunk Purple"),
        ]
        
        def apply_theme_now():
            new_theme = theme_var.get()
            dialog.destroy()  # Close dialog first
            self.root.after(100, lambda: self._apply_theme(new_theme))  # Apply after dialog closes
        
        for theme_id, theme_name in themes:
            ttk.Radiobutton(theme_frame, text=theme_name, variable=theme_var, 
                           value=theme_id).pack(anchor="w", pady=2)
        
        ttk.Button(theme_frame, text="Apply Theme Now", command=apply_theme_now).pack(pady=5)
        
        # Discord webhook settings
        discord_frame = ttk.LabelFrame(frame, text="🔔 Discord Webhook", padding=10)
        discord_frame.pack(fill="x", pady=10)

        ttk.Label(discord_frame, text="Webhook URL:", font=("Arial", 10)).pack(anchor="w")
        webhook_var = tk.StringVar(value=self.discord_webhook_url)
        ttk.Entry(discord_frame, textvariable=webhook_var, width=60).pack(fill="x", pady=5)

        webhook_enabled_var = tk.BooleanVar(value=self.discord_webhook_enabled)
        ttk.Checkbutton(discord_frame, text="Send webhook after each loop", variable=webhook_enabled_var).pack(anchor="w")
        
        # Item detection settings
        item_frame = ttk.LabelFrame(frame, text="🔎 Item Detection", padding=10)
        item_frame.pack(fill="x", pady=10)

        ttk.Button(item_frame, text="Manage Items...", command=self._open_item_manager).pack(anchor="w", pady=(0, 5))

        ttk.Label(item_frame, text="Item webhook URL:", font=("Arial", 10)).pack(anchor="w")
        item_webhook_var = tk.StringVar(value=self.item_webhook_url)
        ttk.Entry(item_frame, textvariable=item_webhook_var, width=60).pack(fill="x", pady=5)

        item_webhook_enabled_var = tk.BooleanVar(value=self.item_webhook_enabled)
        ttk.Checkbutton(item_frame, text="Enable item webhook notifications", variable=item_webhook_enabled_var).pack(anchor="w")
        
        # Option to mention a user when item webhook triggers
        item_mention_var = tk.BooleanVar(value=getattr(self, 'item_webhook_mention_enabled', False))
        ttk.Checkbutton(item_frame, text="Mention user on item webhook", variable=item_mention_var).pack(anchor="w")
        ttk.Label(item_frame, text="Mention username (prefix without @):", font=("Arial", 10)).pack(anchor="w", pady=(6, 0))
        item_mention_user_var = tk.StringVar(value=getattr(self, 'item_webhook_mention_user', ''))
        ttk.Entry(item_frame, textvariable=item_mention_user_var, width=40).pack(fill="x", pady=4)
        
        # Save button
        def save_settings():
            self.loop_count = loop_var.get()
            self.playback_speed = speed_var.get()
            new_theme = theme_var.get()
            
            # Save hotkeys
            self.play_hotkey = play_hotkey_var.get().upper()
            self.record_hotkey = record_hotkey_var.get().upper()

            # Save discord webhook settings
            self.discord_webhook_url = webhook_var.get().strip()
            self.discord_webhook_enabled = webhook_enabled_var.get()

            # Save item detection webhook settings
            self.item_webhook_url = item_webhook_var.get().strip()
            self.item_webhook_enabled = item_webhook_enabled_var.get()
            # Save mention settings
            self.item_webhook_mention_enabled = item_mention_var.get()
            self.item_webhook_mention_user = item_mention_user_var.get().strip()
            
            # If global loop is set to 0 (infinite), set all steps to infinite
            if self.loop_count == 0:
                for step in self.steps:
                    step['step_loop'] = 0
                self._update_steps_display()
            
            self._apply_theme(new_theme)
            self._update_hotkey_buttons()
            self.status_label.config(text=f"Settings: {self.loop_count}x loop, {self.playback_speed:.1f}x speed | Play: {self.play_hotkey}, Record: {self.record_hotkey}")
            dialog.destroy()
        
        ttk.Button(frame, text="Save Settings", command=save_settings).pack(pady=20)
    
    def _apply_theme(self, theme_name):
        """Apply a theme to the application"""
        self.current_theme = theme_name

    def _open_guide(self):
        """Open a comprehensive user guide in a dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Simple Macro — Guide")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Arial", 10))
        text.pack(fill="both", expand=True, padx=10, pady=10)

        guide = (
            "Simple Macro — User Guide\n"
            "\n"
            "Welcome:\n"
            "- This guide explains how to use Simple Macro to automate repetitive tasks safely and reliably.\n"
            "- Read each section and try small, simple macros first.\n"
            "\n"
            "Getting Started:\n"
            "- Add a new step with '➕ New Step'. Most users start with simple clicks and short delays (0.2–1.0s).\n"
            "- Use '📍 Select Coordinates' to pick precise screen positions. The picker shows live screen coordinates.\n"
            "- Save macros with '💾 Save' and load them with '📂 Load'. Saved files are standard JSON and can be shared.\n"
            "\n"
            "Core Concepts (Steps & Playback):\n"
            "- Steps are executed in order. Each step supports a small delay after it finishes — use this to wait for UI updates.\n"
            "- Step types: Click (single/multiple clicks), Hold (press-and-hold for seconds), Type (send text), Scroll, and Image Search (wait for image).\n"
            "- Global playback options (Settings) control loop count and overall speed. Per-step loop and speed let you fine-tune repeats and timing.\n"
            "\n"
            "QuickRec (Recording):\n"
            "- Press the record hotkey (default F7) once to start QuickRec and press it again to stop. QuickRec captures mouse and keyboard events.\n"
            "- The recorder ignores interactions inside the app to avoid recording control clicks.\n"
            "- After recording, review the converted steps and edit any coordinates, delays, or key names before saving.\n"
            "\n"
            "Image Search Steps (Wait-for-Image):\n"
            "- Use Image Search when you need the macro to wait for a visual element (button, icon, or item) to appear.\n"
            "- Capture a clear, tightly-cropped sample of the element and save it to your Images folder (Manage Items helps with this).\n"
            "- Confidence: Try 0.80 first. If the macro misses matches, lower the confidence slightly (e.g., 0.75). If there are false matches, raise it.\n"
            "- Timeout: Use a finite timeout (e.g., 10–30s) for predictable behavior. 0 = wait forever, which may hang your macro.\n"
            "- Click options: configure whether the macro should click the found location and how many times. Use small click counts (1–3) to be safe.\n"
            "\n"
            "Item Detection & Notifications (For Users):\n"
            "- Item Detection runs in the background and watches for images you add in Manage Items. When an item is detected, the app can send a notification (Discord webhook) with a screenshot.\n"
            "- To enable notifications: open Settings → Item Detection, set the webhook URL, and enable item webhook notifications.\n"
            "- Mentioning a user: to actually ping someone on Discord, enter their numeric Discord user ID (a long number) in the "
            "Mention username" " field and enable the Mention option. The app sends the mention as <@USER_ID> with proper allowed_mentions so the ping works.\n"
            "  - If you don't know the numeric ID: ask the person to enable Developer Mode in Discord (User Settings → Advanced), then right-click their name and choose 'Copy ID'.\n"
            "\n"
            "Loop Notifications (User-friendly):\n"
            "- If "
            "Send webhook after each loop" " is enabled, the app will send a short summary and a screenshot when a full playback loop finishes.\n"
            "- Use this for long-running macros so you can be alerted when cycles complete.\n"
            "\n"
            "Safe Usage & Best Practices:\n"
            "- Test macros on a small scale before running large loops — use 1–3 loops and watch the result.\n"
            "- Avoid running macros while other critical applications are active (banking, video calls, games that prohibit automation).\n"
            "- If a macro interacts with sensitive UI (financial, personal), run it manually or add extra confirmation steps.\n"
            "- Prefer coordinates anchored to stable UI elements (e.g., images) rather than absolute screen positions if you use multiple monitors or change resolution.\n"
            "\n"
            "Troubleshooting (User-focused):\n"
            "- If the macro clicks the wrong place: re-capture the coordinate with the picker and increase delay after the step.\n"
            "- If Image Search never finds the target: capture a clearer sample, increase confidence tolerance, or broaden the search area.\n"
            "- If notifications don't arrive: check your webhook URL (no extra spaces), ensure the receiving service is online, and verify any Discord roles/permissions.\n"
            "- If the app cannot capture the screen on Windows: make sure any privacy settings (Windows 10/11) allow screen capture for desktop apps.\n"
            "\n"
            "Examples (Simple Macros):\n"
            "- Example 1 — Click a button every 10 seconds (3 times): New Step: Click at target coordinates → Delay 10.0 → Set loop count 3.\n"
            "- Example 2 — Wait for a 'Ready' image then click: Add Image Search step with small crop of 'Ready' indicator, confidence 0.85, timeout 20s, Click when found.\n"
            "- Example 3 — Type text into a field: Add Step → Type → text: 'Hello, world!' → Delay 0.5.\n"
            "\n"
            "Advanced Tips (User-level, optional):\n"
            "- Use per-step speed multipliers for tiny timing tweaks instead of changing the global speed.\n"
            "- Use per-step loops to repeat a subset of steps without looping the whole macro.\n"
            "- Keep images for Image Search in the Images/Items folder so they are easy to manage.\n"
            "\n"
            "Where to get help:\n"
            "- Use the Logs tab to see what the app is doing; it helps diagnose missed clicks or failed searches.\n"
            "- If you need more help, export your macro (Save) and share it with a support contact along with a short description of what went wrong.\n"
            "\n"
            "Final Notes:\n"
            "- Start small, iterate, and keep backups of macros you care about.\n"
            "- The app is intended to help automate routine tasks — keep safety and privacy in mind.\n"
        )

        text.insert("1.0", guide)
        text.config(state=tk.DISABLED)
        
        # Theme color definitions
        themes = {
            "dark": {
                "bg": "#1c1c1c",
                "fg": "#ffffff",
                "listbox_bg": "#2d2d2d",
                "listbox_fg": "#ffffff",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "accent": "#0078d4",
                "use_sv_ttk": "dark"
            },
            "light": {
                "bg": "#fafafa",
                "fg": "#000000",
                "listbox_bg": "#ffffff",
                "listbox_fg": "#000000",
                "select_bg": "#0078d4",
                "select_fg": "#ffffff",
                "accent": "#0078d4",
                "use_sv_ttk": "light"
            },
            "ocean": {
                "bg": "#0a1929",
                "fg": "#b2ebf2",
                "listbox_bg": "#0d2137",
                "listbox_fg": "#4dd0e1",
                "select_bg": "#00838f",
                "select_fg": "#ffffff",
                "accent": "#00bcd4",
                "use_sv_ttk": "dark"
            },
            "forest": {
                "bg": "#1b2e1b",
                "fg": "#c8e6c9",
                "listbox_bg": "#2e4a2e",
                "listbox_fg": "#81c784",
                "select_bg": "#2e7d32",
                "select_fg": "#ffffff",
                "accent": "#4caf50",
                "use_sv_ttk": "dark"
            },
            "sunset": {
                "bg": "#2d1f1f",
                "fg": "#ffccbc",
                "listbox_bg": "#3e2723",
                "listbox_fg": "#ffab91",
                "select_bg": "#e65100",
                "select_fg": "#ffffff",
                "accent": "#ff5722",
                "use_sv_ttk": "dark"
            },
            "cyberpunk": {
                "bg": "#1a0a2e",
                "fg": "#e1bee7",
                "listbox_bg": "#2d1b4e",
                "listbox_fg": "#ce93d8",
                "select_bg": "#7b1fa2",
                "select_fg": "#ffffff",
                "accent": "#9c27b0",
                "use_sv_ttk": "dark"
            }
        }
        
        # Resolve theme name from current setting (fallback to dark)
        theme_name = getattr(self, 'current_theme', 'dark')
        # Get theme colors (default to dark if not found)
        theme = themes.get(theme_name, themes["dark"])
        
        # Apply Sun Valley base theme first
        if theme["use_sv_ttk"] == "light":
            sv_ttk.use_light_theme()
        else:
            sv_ttk.use_dark_theme()
        
        # Force update to apply sv_ttk changes
        self.root.update_idletasks()
        
        # Apply custom colors on top
        self.root.configure(bg=theme["bg"])
        
        # Configure ttk styles with custom colors
        style = ttk.Style()
        
        # Override all frame backgrounds
        style.configure("TFrame", background=theme["bg"])
        style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
        style.configure("TLabelframe", background=theme["bg"], bordercolor=theme["accent"])
        style.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["fg"])
        
        # Button styling
        style.configure("TButton", background=theme["accent"], foreground=theme["fg"])
        style.map("TButton", 
                  background=[("active", theme["select_bg"]), ("pressed", theme["select_bg"])],
                  foreground=[("active", theme["select_fg"])])
        
        # Radiobutton and Checkbutton
        style.configure("TRadiobutton", background=theme["bg"], foreground=theme["fg"])
        style.configure("TCheckbutton", background=theme["bg"], foreground=theme["fg"])
        
        # Entry and Spinbox
        style.configure("TEntry", fieldbackground=theme["listbox_bg"], foreground=theme["listbox_fg"])
        style.configure("TSpinbox", fieldbackground=theme["listbox_bg"], foreground=theme["listbox_fg"])
        
        # Scrollbar
        style.configure("TScrollbar", background=theme["accent"], troughcolor=theme["bg"])
        
        # Notebook (tabs)
        style.configure("TNotebook", background=theme["bg"])
        style.configure("TNotebook.Tab", background=theme["bg"], foreground=theme["fg"])
        
        # Scale/Slider
        style.configure("TScale", background=theme["bg"], troughcolor=theme["listbox_bg"])
        
        # Listbox styling (tk widget, not ttk)
        self.steps_listbox.configure(
            bg=theme["listbox_bg"],
            fg=theme["listbox_fg"],
            selectbackground=theme["select_bg"],
            selectforeground=theme["select_fg"],
            highlightbackground=theme["accent"],
            highlightcolor=theme["accent"]
        )
        
        # Apply colors to all existing widgets recursively
        self._apply_colors_to_children(self.root, theme)
        
        self.status_label.config(text=f"Theme: {theme_name.capitalize()} applied")
    
    def _apply_colors_to_children(self, parent, theme):
        """Recursively apply theme colors to all child widgets"""
        for widget in parent.winfo_children():
            try:
                widget_class = widget.winfo_class()
                
                # Handle tk widgets (not ttk)
                if widget_class == 'Frame':
                    widget.configure(bg=theme["bg"])
                elif widget_class == 'Label':
                    widget.configure(bg=theme["bg"], fg=theme["fg"])
                elif widget_class == 'Listbox':
                    widget.configure(bg=theme["listbox_bg"], fg=theme["listbox_fg"],
                                    selectbackground=theme["select_bg"], selectforeground=theme["select_fg"])
                elif widget_class == 'Entry':
                    widget.configure(bg=theme["listbox_bg"], fg=theme["listbox_fg"],
                                    insertbackground=theme["fg"])
                elif widget_class == 'Text':
                    widget.configure(bg=theme["listbox_bg"], fg=theme["listbox_fg"],
                                    insertbackground=theme["fg"])
                elif widget_class == 'Canvas':
                    widget.configure(bg=theme["bg"])
                
                # Recurse into children
                self._apply_colors_to_children(widget, theme)
            except Exception:
                pass

    def _compute_image_hash(self, path_or_bytes):
        """Compute SHA256 hash for a file path or bytes-like object.

        Returns hex digest string or None on error.
        """
        try:
            if isinstance(path_or_bytes, (bytes, bytearray)):
                data = path_or_bytes
            else:
                p = Path(str(path_or_bytes))
                if not p.exists():
                    return None
                with open(p, 'rb') as f:
                    data = f.read()
            h = hashlib.sha256()
            h.update(data)
            return h.hexdigest()
        except Exception:
            return None

    def _find_image_by_hash(self, img_hash):
        """Search `self.images_folder` recursively for a file whose SHA256 hash matches `img_hash`.

        Returns Path or None.
        """
        try:
            base = Path(self.images_folder)
            if not base.exists():
                return None
            for p in base.rglob('*'):
                if p.is_file():
                    try:
                        if self._compute_image_hash(p) == img_hash:
                            return p
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def _open_item_manager(self):
        """Dialog to manage item detection images and names."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Item Manager")
        dialog.geometry("600x420")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        lb = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        lb.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=lb.yview)

        def refresh_list():
            lb.delete(0, tk.END)
            for idx, item in enumerate(self.item_detection_items):
                name = item.get('name', 'unnamed')
                enabled = '✓' if item.get('enabled', True) else '✗'
                lb.insert(tk.END, f"{idx+1}. {name} [{enabled}]")

        def add_item():
            pick = filedialog.askopenfilename(title='Select item image', filetypes=[('Image','*.png;*.jpg;*.bmp')])
            if not pick:
                return
            src = Path(pick)
            dest_dir = self.images_folder / 'items'
            dest_dir.mkdir(exist_ok=True)
            dest = dest_dir / src.name
            shutil.copy(pick, dest)

            subdialog = tk.Toplevel(dialog)
            subdialog.title('Item Details')
            subdialog.transient(dialog)
            ttk.Label(subdialog, text='Item name:').pack(padx=10, pady=(10,0))
            name_var = tk.StringVar(value=src.stem)
            ttk.Entry(subdialog, textvariable=name_var, width=40).pack(padx=10, pady=5)
            ttk.Label(subdialog, text='Confidence (0.5-1.0):').pack(padx=10)
            conf_var = tk.DoubleVar(value=0.8)
            ttk.Entry(subdialog, textvariable=conf_var, width=10).pack(padx=10, pady=5)

            def save_item():
                image_hash = self._compute_image_hash(dest)
                self.item_detection_items.append({
                    'image_path': str(dest),
                    'image_hash': image_hash,
                    'name': name_var.get().strip() or src.stem,
                    'confidence': float(conf_var.get()),
                    'enabled': True,
                    'last_detected': 0,
                    'cooldown': 10
                })
                subdialog.destroy()
                refresh_list()

            ttk.Button(subdialog, text='Save', command=save_item).pack(pady=10)

        def remove_item():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            del self.item_detection_items[idx]
            refresh_list()

        def toggle_enabled():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            item = self.item_detection_items[idx]
            item['enabled'] = not item.get('enabled', True)
            refresh_list()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=8)
        ttk.Button(btn_frame, text='Add Item', command=add_item).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Remove', command=remove_item).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Toggle Enabled', command=toggle_enabled).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Close', command=dialog.destroy).pack(side='right', padx=5)

        refresh_list()

    def _send_discord_webhook(self, content=None):
        """Send a Discord webhook asynchronously. If `content` is None no message body is added (placeholder).

        The webhook will only be sent if `self.discord_webhook_url` is set and `self.discord_webhook_enabled` is True.
        """
        if not self.discord_webhook_url or not self.discord_webhook_enabled:
            return

        def _do_send():
            try:
                # Import here to avoid hard dependency at module import time
                import requests as _requests

                payload = {}
                # Send minimal content if provided
                if content is not None:
                    payload['content'] = content
                else:
                    payload['content'] = ""

                _requests.post(self.discord_webhook_url, json=payload, timeout=6)
            except Exception as e:
                print(f"Discord webhook error: {e}")

        threading.Thread(target=_do_send, daemon=True).start()

    def _notify_loop_complete(self, loop_number: int):
        """Called when a macro loop completes. Currently does not set the message body."""
        if not self.discord_webhook_url or not self.discord_webhook_enabled:
            return

        def _do_notify():
            try:
                # Take a screenshot of the primary monitor
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    sct_img = sct.grab(monitor)

                # Convert to PIL Image
                img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')

                # Save to bytes
                bio = io.BytesIO()
                img.save(bio, format='PNG')
                bio.seek(0)

                # Build embed content
                total_loops = '∞' if self.loop_count == 0 else str(self.loop_count)
                description = f"Loops completed: {loop_number} / {total_loops}"

                embed = {
                    "title": "Loop Complete",
                    "description": description,
                    "image": {"url": "attachment://screenshot.png"}
                }

                payload = {
                    "embeds": [embed]
                }

                files = {
                    'file': ('screenshot.png', bio, 'image/png')
                }

                # Send multipart/form-data with payload_json as string
                requests.post(self.discord_webhook_url, data={"payload_json": json.dumps(payload)}, files=files, timeout=10)
            except Exception as e:
                print(f"Discord webhook notify error: {e}")

        threading.Thread(target=_do_notify, daemon=True).start()

    def _send_item_webhook(self, item_name: str, image_pil: Image.Image):
        """Send an item-obtained webhook with screenshot attachment."""
        if not self.item_webhook_url or not self.item_webhook_enabled:
            return
        try:
            bio = io.BytesIO()
            image_pil.save(bio, format='PNG')
            bio.seek(0)

            # Build content with optional mention (use numeric ID if provided)
            mention_text = ""
            allowed_mentions = None
            try:
                if getattr(self, 'item_webhook_mention_enabled', False):
                    user = getattr(self, 'item_webhook_mention_user', '').strip()
                    if user:
                        # If user is numeric, use proper mention syntax so Discord pings the user
                        if user.isdigit():
                            mention_text = f"<@{user}> "
                            allowed_mentions = {"users": [user]}
                        else:
                            # Fallback to plain @username prefix (best-effort, won't ping reliably)
                            mention_text = f"@{user} "
            except Exception:
                mention_text = ""

            content = f"{mention_text}Item ({item_name}) obtained!"

            embed = {
                "title": f"Item ({item_name}) obtained!",
                "description": f"Item: {item_name}",
                "image": {"url": "attachment://screenshot.png"}
            }

            payload = {"content": content, "embeds": [embed]}
            if allowed_mentions:
                payload["allowed_mentions"] = allowed_mentions

            # Send synchronously to ensure screenshot corresponds to detection moment
            requests.post(self.item_webhook_url, data={"payload_json": json.dumps(payload)}, files={'file': ('screenshot.png', bio, 'image/png')}, timeout=10)
        except Exception as e:
            print(f"Item webhook error: {e}")

    def _start_item_detector(self):
        """Start the background item detection thread."""
        def _loop():
            while True:
                try:
                    # small pause between cycles
                    time.sleep(1.0)

                    # iterate configured items
                    for item in list(self.item_detection_items):
                        try:
                            if not item.get('enabled', True):
                                continue

                            confidence = item.get('confidence', 0.8)
                            image_path = item.get('image_path')
                            if not image_path:
                                continue

                            res = self._search_for_image(image_path, confidence)
                            if res:
                                now = time.time()
                                last = item.get('last_detected', 0)
                                cooldown = item.get('cooldown', 10)
                                if now - last >= cooldown:
                                    # capture screenshot and send webhook
                                    with mss.mss() as sct:
                                        monitor = sct.monitors[1]
                                        sct_img = sct.grab(monitor)
                                    pil_img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
                                    self._send_item_webhook(item.get('name', 'item'), pil_img)
                                    item['last_detected'] = now
                        except Exception:
                            pass
                except Exception:
                    pass

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
    
    def _add_image_search_step(self):
        """Add an image search conditional step"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Image Search Step")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create scrollable frame
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding=20)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = scrollable_frame
        
        ttk.Label(frame, text="🔍 Image Search Step", font=("Arial", 14, "bold")).pack(pady=(0, 15))
        ttk.Label(frame, text="Execute actions when an image is found on screen", font=("Arial", 10)).pack(pady=(0, 15))
        
        # Step name (optional)
        name_frame = ttk.Frame(frame)
        name_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(name_frame, text="Step Name (optional):", font=("Arial", 10, "bold")).pack(anchor="w")
        step_name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=step_name_var, font=("Arial", 10), width=30).pack(anchor="w", pady=(5, 0))
        
        # Image selection
        image_frame = ttk.LabelFrame(frame, text="Image to Find", padding=10)
        image_frame.pack(fill="x", pady=10)
        
        image_path_var = tk.StringVar()
        image_name_var = tk.StringVar(value="No image selected")
        
        ttk.Label(image_frame, textvariable=image_name_var, font=("Arial", 10)).pack(anchor="w")
        
        # Image preview label
        preview_label = ttk.Label(image_frame)
        preview_label.pack(pady=10)
        
        def select_image():
            filepath = filedialog.askopenfilename(
                title="Select Image",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
            )
            if filepath:
                # Copy to macro_images folder
                src_path = Path(filepath)
                dest_path = self.images_folder / src_path.name
                
                # Copy the file
                shutil.copy(filepath, dest_path)
                
                image_path_var.set(str(dest_path))
                image_name_var.set(src_path.name)
                
                # Show preview
                img = Image.open(filepath)
                img.thumbnail((150, 150))
                img_tk = ImageTk.PhotoImage(img)
                preview_label.config(image=img_tk)
                preview_label.image = img_tk
        
        ttk.Button(image_frame, text="📁 Select Image", command=select_image).pack(anchor="w")
        
        # Confidence threshold
        conf_frame = ttk.LabelFrame(frame, text="Detection Settings", padding=10)
        conf_frame.pack(fill="x", pady=10)
        
        ttk.Label(conf_frame, text="Confidence Threshold:", font=("Arial", 10)).pack(anchor="w")
        
        conf_var = tk.DoubleVar(value=0.8)
        conf_label = ttk.Label(conf_frame, text="0.80", font=("Arial", 10, "bold"))
        conf_label.pack(anchor="e")
        
        def update_conf_label(val):
            conf_label.config(text=f"{float(val):.2f}")
        
        conf_slider = ttk.Scale(conf_frame, from_=0.5, to=1.0, variable=conf_var,
                               orient="horizontal", command=update_conf_label)
        conf_slider.pack(fill="x")
        
        # Click on image option
        click_frame = ttk.LabelFrame(frame, text="Click Action", padding=10)
        click_frame.pack(fill="x", pady=10)

        click_image_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(click_frame, text="Click when image is found", variable=click_image_var).pack(anchor="w")

        # Click count
        click_count_row = ttk.Frame(click_frame)
        click_count_row.pack(fill="x", pady=5)
        ttk.Label(click_count_row, text="Click Count:", font=("Arial", 10)).pack(side="left")
        click_count_var = tk.IntVar(value=1)
        ttk.Spinbox(click_count_row, from_=1, to=100, textvariable=click_count_var, width=8).pack(side="left", padx=5)
        
        # Click mode selection
        click_mode_var = tk.StringVar(value="offset")
        
        mode_frame = ttk.Frame(click_frame)
        mode_frame.pack(fill="x", pady=5)
        
        ttk.Radiobutton(mode_frame, text="Use offset from image center", 
                       variable=click_mode_var, value="offset").pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="Use absolute coordinates", 
                       variable=click_mode_var, value="absolute").pack(anchor="w")
        
        # Offset section
        offset_section = ttk.Frame(click_frame)
        
        offset_row = ttk.Frame(offset_section)
        offset_row.pack(fill="x", pady=5)
        
        ttk.Label(offset_row, text="X Offset (pixels):", font=("Arial", 10)).pack(side="left")
        offset_x_var = tk.IntVar(value=0)
        ttk.Spinbox(offset_row, from_=-500, to=500, textvariable=offset_x_var, width=8).pack(side="left", padx=5)
        
        ttk.Label(offset_row, text="Y Offset:", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        offset_y_var = tk.IntVar(value=0)
        ttk.Spinbox(offset_row, from_=-500, to=500, textvariable=offset_y_var, width=8).pack(side="left", padx=5)
        
        # Absolute coordinates section
        abs_section = ttk.Frame(click_frame)
        
        abs_row = ttk.Frame(abs_section)
        abs_row.pack(fill="x", pady=5)
        
        ttk.Label(abs_row, text="X:", font=("Arial", 10)).pack(side="left")
        abs_x_var = tk.StringVar(value="0")
        ttk.Entry(abs_row, textvariable=abs_x_var, width=8).pack(side="left", padx=5)
        
        ttk.Label(abs_row, text="Y:", font=("Arial", 10)).pack(side="left", padx=(20, 0))
        abs_y_var = tk.StringVar(value="0")
        ttk.Entry(abs_row, textvariable=abs_y_var, width=8).pack(side="left", padx=5)
        
        # Store dialog reference for coordinate picker
        self._image_search_dialog = dialog
        
        select_coords_btn = ttk.Button(
            abs_section,
            text="📍 Select Coordinates",
            command=lambda: self._open_coordinate_picker(abs_x_var, abs_y_var, dialog)
        )
        select_coords_btn.pack(anchor="w", pady=5)
        
        def toggle_click_mode(*args):
            if click_mode_var.get() == "offset":
                abs_section.pack_forget()
                offset_section.pack(fill="x", pady=5)
            else:
                offset_section.pack_forget()
                abs_section.pack(fill="x", pady=5)
        
        click_mode_var.trace('w', toggle_click_mode)
        toggle_click_mode()  # Initialize
        
        # Search timeout
        timeout_frame = ttk.LabelFrame(frame, text="Search Timeout", padding=10)
        timeout_frame.pack(fill="x", pady=10)
        
        ttk.Label(timeout_frame, text="Wait for image (seconds):", font=("Arial", 10)).pack(anchor="w")
        ttk.Label(timeout_frame, text="(0 = wait forever until found)", font=("Arial", 8)).pack(anchor="w")
        
        timeout_var = tk.StringVar(value="30")
        ttk.Entry(timeout_frame, textvariable=timeout_var, width=10).pack(anchor="w", pady=5)
        # On-timeout behavior
        on_timeout_var = tk.StringVar(value="move_on")
        ttk.Label(timeout_frame, text="On timeout:", font=("Arial", 10)).pack(anchor="w", pady=(8,0))
        on_to_frame = ttk.Frame(timeout_frame)
        on_to_frame.pack(fill="x", pady=2)
        ttk.Radiobutton(on_to_frame, text="Move on to next step", variable=on_timeout_var, value="move_on").pack(anchor="w")
        ttk.Radiobutton(on_to_frame, text="Retry search after timeout", variable=on_timeout_var, value="retry").pack(anchor="w")
        
        # Delay
        delay_frame = ttk.Frame(frame)
        delay_frame.pack(fill="x", pady=10)
        
        ttk.Label(delay_frame, text="Delay After (seconds):", font=("Arial", 11)).pack(side="left")
        delay_var = tk.StringVar(value="0.5")
        ttk.Entry(delay_frame, textvariable=delay_var, width=10).pack(side="right")
        
        # Add step button
        def add_step():
            if not image_path_var.get():
                messagebox.showerror("Error", "Please select an image!")
                return
            
            try:
                delay = float(delay_var.get())
            except ValueError:
                messagebox.showerror("Error", "Delay must be a number!")
                return
            
            try:
                search_timeout = float(timeout_var.get())
            except ValueError:
                messagebox.showerror("Error", "Timeout must be a number!")
                return
            
            step = {
                'action': 'image_search',
                'image_path': image_path_var.get(),
                'image_name': image_name_var.get(),
                'image_hash': None,
                'confidence': conf_var.get(),
                'click_image': click_image_var.get(),
                'click_count': click_count_var.get(),
                'click_mode': click_mode_var.get(),
                'offset_x': offset_x_var.get(),
                'offset_y': offset_y_var.get(),
                'delay': delay,
                'search_timeout': search_timeout,
                'on_timeout': on_timeout_var.get(),
                'name': step_name_var.get().strip()
            }
            
            # Add absolute coordinates if using that mode
            if click_mode_var.get() == "absolute":
                try:
                    step['abs_x'] = int(abs_x_var.get())
                    step['abs_y'] = int(abs_y_var.get())
                except ValueError:
                    messagebox.showerror("Error", "Coordinates must be numbers!")
                    return
            
            # Compute and store image hash so saved macro matches by pixels instead of filename
            try:
                img_hash = self._compute_image_hash(step['image_path'])
                step['image_hash'] = img_hash
            except Exception:
                step['image_hash'] = None

            self.steps.append(step)
            self._update_steps_display()
            dialog.destroy()
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=15)
        
        ttk.Button(button_frame, text="Add Step", command=add_step).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)
    
    def _search_for_image(self, image_path, confidence=0.8):
        """Search for an image on screen and return center coordinates if found"""
        try:
            # Take screenshot
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                screen_img = np.array(screenshot)
                screen_img = cv2.cvtColor(screen_img, cv2.COLOR_BGRA2BGR)
            
            # Load template
            template = cv2.imread(image_path)
            if template is None:
                return None
            
            # Template matching
            result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= confidence:
                # Calculate center of found image
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return (center_x, center_y, max_val)
            
            return None
        except Exception as e:
            print(f"Image search error: {e}")
            return None

    def _start_recording_dialog(self):
        """Open dialog to start recording"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Macro")
        dialog.geometry("450x380")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        
        ttk.Label(frame, text="🎬 Record Macro", font=("Arial", 14, "bold")).pack(pady=(0, 10))
        
        ttk.Label(frame, text="This will record your mouse clicks and keyboard inputs.", 
                 font=("Arial", 10)).pack(pady=(0, 5))
        ttk.Label(frame, text=f"Press {self.record_hotkey} to stop recording.", 
                 font=("Arial", 10, "bold")).pack(pady=(0, 15))
        
        # Options
        options_frame = ttk.LabelFrame(frame, text="Recording Options", padding=10)
        options_frame.pack(fill="x", pady=(0, 15))
        
        record_mouse_moves = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Record mouse movements (creates many steps)", 
                       variable=record_mouse_moves).pack(anchor="w")
        
        record_clicks = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Record mouse clicks", 
                       variable=record_clicks).pack(anchor="w")
        
        record_scroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Record mouse scroll", 
                       variable=record_scroll).pack(anchor="w")
        
        record_keys = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Record keyboard inputs", 
                       variable=record_keys).pack(anchor="w")
        
        # Status label
        status_var = tk.StringVar(value="Ready to record")
        status_label = ttk.Label(frame, textvariable=status_var, font=("Arial", 10))
        status_label.pack(pady=10)
        
        # Store options for recording
        self.record_options = {
            'mouse_moves': record_mouse_moves,
            'clicks': record_clicks,
            'scroll': record_scroll,
            'keys': record_keys
        }
        
        def start_recording():
            dialog.withdraw()
            self.root.withdraw()
            time.sleep(0.5)  # Give time to hide windows
            
            self.recorded_events = []
            self.record_start_time = time.time()
            self.recording = True
            
            # Start listeners
            self.mouse_listener = MouseListener(
                on_click=self._on_record_click,
                on_move=self._on_record_move if record_mouse_moves.get() else None,
                on_scroll=self._on_record_scroll if record_scroll.get() else None
            )
            self.keyboard_listener = KeyboardListener(
                on_press=self._on_record_key_press,
                on_release=self._on_record_key_release
            )
            
            self.mouse_listener.start()
            self.keyboard_listener.start()
            
            # Show recording indicator
            self._show_recording_indicator(dialog)
        
        def cancel():
            dialog.destroy()
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(15, 0))
        
        # Create larger styled buttons
        style = ttk.Style()
        style.configure("Big.TButton", font=("Arial", 12), padding=(20, 15))
        
        start_btn = ttk.Button(button_frame, text="🔴 Start Recording", command=start_recording, style="Big.TButton")
        start_btn.pack(side="left", padx=5, expand=True, fill="x", ipady=10)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=cancel, style="Big.TButton")
        cancel_btn.pack(side="left", padx=5, expand=True, fill="x", ipady=10)
    
    def _show_recording_indicator(self, parent_dialog):
        """Show a small indicator that recording is in progress"""
        indicator = tk.Toplevel()
        indicator.title("Recording...")
        indicator.geometry("250x80")
        indicator.attributes('-topmost', True)
        indicator.overrideredirect(True)  # No window decorations
        
        # Position at top-right corner
        screen_width = indicator.winfo_screenwidth()
        indicator.geometry(f"+{screen_width - 270}+20")
        
        frame = tk.Frame(indicator, bg="#e74c3c", padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        
        tk.Label(frame, text="🔴 RECORDING", font=("Arial", 12, "bold"), 
                bg="#e74c3c", fg="white").pack()
        tk.Label(frame, text=f"Press {self.record_hotkey} to stop", font=("Arial", 10), 
                bg="#e74c3c", fg="white").pack()
        
        self.recording_indicator = indicator
        self.parent_dialog = parent_dialog
        
        # Check for F9 to stop
        def check_stop():
            if self.recording:
                indicator.after(100, check_stop)
            else:
                indicator.destroy()
                self._stop_recording()
        
        indicator.after(100, check_stop)
    
    def _on_record_click(self, x, y, button, pressed):
        """Handle mouse click during recording"""
        if not self.recording:
            return
        
        if not self.record_options['clicks'].get():
            return
        
        # Ignore clicks that occur inside the app window itself
        try:
            if self._is_point_inside_window(x, y):
                return
        except Exception:
            pass
        
        timestamp = time.time() - self.record_start_time
        
        self.recorded_events.append({
            'type': 'mouse_click',
            'timestamp': timestamp,
            'x': x,
            'y': y,
            'button': 'left_click' if button == Button.left else 'right_click',
            'pressed': pressed
        })
    
    def _on_record_move(self, x, y):
        """Handle mouse move during recording"""
        if not self.recording:
            return
        
        # Ignore moves inside the app window
        try:
            if self._is_point_inside_window(x, y):
                return
        except Exception:
            pass
        
        timestamp = time.time() - self.record_start_time
        
        self.recorded_events.append({
            'type': 'mouse_move',
            'timestamp': timestamp,
            'x': x,
            'y': y
        })
    
    def _on_record_scroll(self, x, y, dx, dy):
        """Handle mouse scroll during recording"""
        if not self.recording:
            return
        
        if not self.record_options.get('scroll', tk.BooleanVar(value=True)).get():
            return
        
        # Ignore scrolls inside the app window
        try:
            if self._is_point_inside_window(x, y):
                return
        except Exception:
            pass
        
        timestamp = time.time() - self.record_start_time
        
        self.recorded_events.append({
            'type': 'mouse_scroll',
            'timestamp': timestamp,
            'x': x,
            'y': y,
            'dx': dx,
            'dy': dy  # positive = scroll up, negative = scroll down
        })
    
    def _on_record_key_press(self, key):
        """Handle key press during recording"""
        if not self.recording:
            return
        
        # Do NOT handle the record hotkey here; only the global hotkey listener should toggle recording
        
        if not self.record_options['keys'].get():
            return
        
        timestamp = time.time() - self.record_start_time
        
        try:
            key_str = key.char if hasattr(key, 'char') and key.char else str(key).replace('Key.', '')
        except AttributeError:
            key_str = str(key).replace('Key.', '')
        
        self.recorded_events.append({
            'type': 'key_press',
            'timestamp': timestamp,
            'key': key_str
        })
    
    def _on_record_key_release(self, key):
        """Handle key release during recording"""
        if not self.recording:
            return
        
        # Do NOT handle the record hotkey here; only the global hotkey listener should toggle recording
        
        if not self.record_options['keys'].get():
            return
        
        timestamp = time.time() - self.record_start_time
        
        try:
            key_str = key.char if hasattr(key, 'char') and key.char else str(key).replace('Key.', '')
        except AttributeError:
            key_str = str(key).replace('Key.', '')
        
        self.recorded_events.append({
            'type': 'key_release',
            'timestamp': timestamp,
            'key': key_str
        })
    
    def _stop_recording(self):
        """Stop recording and convert events to steps"""
        # Stop listeners
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        # Show windows again
        self.root.deiconify()
        if hasattr(self, 'parent_dialog'):
            self.parent_dialog.destroy()
        
        # Convert events to steps
        if self.recorded_events:
            self._convert_events_to_steps()
            messagebox.showinfo("Recording Complete", 
                              f"Recorded {len(self.recorded_events)} events.\n"
                              f"Converted to {len(self.steps)} steps.")
        else:
            messagebox.showinfo("Recording Complete", "No events were recorded.")
        
        self._update_steps_display()
    
    def _convert_events_to_steps(self):
        """Convert recorded events into macro steps"""
        if not self.recorded_events:
            return
        
        # Sort events by timestamp
        events = sorted(self.recorded_events, key=lambda e: e['timestamp'])
        
        new_steps = []
        last_timestamp = 0
        
        # Track key states for hold detection
        key_press_times = {}
        
        i = 0
        while i < len(events):
            event = events[i]
            
            # Calculate delay from previous event
            delay = round(event['timestamp'] - last_timestamp, 2)
            if delay < 0.01:
                delay = 0.05  # Minimum delay
            
            if event['type'] == 'mouse_click':
                if event['pressed']:
                    # Look for the release to determine if it's a click or hold
                    release_event = None
                    for j in range(i + 1, len(events)):
                        if (events[j]['type'] == 'mouse_click' and 
                            events[j]['button'] == event['button'] and 
                            not events[j]['pressed']):
                            release_event = events[j]
                            break
                    
                    if release_event:
                        hold_duration = release_event['timestamp'] - event['timestamp']
                        
                        if hold_duration > 0.3:  # Considered a hold if > 300ms
                            step_item = {
                                'action': 'hold',
                                'key': event['button'],
                                'x': event['x'],
                                'y': event['y'],
                                'amount': round(hold_duration, 2),
                                'delay': delay
                            }
                        else:
                            step_item = {
                                'action': 'click',
                                'key': event['button'],
                                'x': event['x'],
                                'y': event['y'],
                                'amount': 1,
                                'delay': delay
                            }
                        new_steps.append(step_item)
                        try:
                            self._log(f"Converted event -> step: {step_item}")
                        except Exception:
                            pass
                    
                    last_timestamp = event['timestamp']
            
            elif event['type'] == 'key_press':
                key = event['key']

                # Look for a matching key_release after this press
                release_event = None
                for j in range(i + 1, len(events)):
                    if events[j]['type'] == 'key_release' and events[j]['key'] == key:
                        release_event = events[j]
                        break

                if release_event:
                    hold_duration = release_event['timestamp'] - event['timestamp']
                    if hold_duration > 0.3:  # Considered a hold
                        step_item = {
                            'action': 'hold',
                            'key': key,
                            'amount': round(hold_duration, 2),
                            'delay': delay
                        }
                    else:
                        step_item = {
                            'action': 'click',
                            'key': key,
                            'amount': 1,
                            'delay': delay
                        }
                    new_steps.append(step_item)
                    try:
                        self._log(f"Converted event -> step: {step_item}")
                    except Exception:
                        pass
                else:
                    # No release found, treat as a simple click
                    step_item = {
                        'action': 'click',
                        'key': key,
                        'amount': 1,
                        'delay': delay
                    }
                    new_steps.append(step_item)
                    try:
                        self._log(f"Converted event -> step: {step_item}")
                    except Exception:
                        pass

                last_timestamp = event['timestamp']
            
            elif event['type'] == 'mouse_move':
                # Group consecutive mouse moves
                step_item = {
                    'action': 'click',
                    'key': 'mouse_move',
                    'x': event['x'],
                    'y': event['y'],
                    'amount': 1,
                    'delay': delay
                }
                new_steps.append(step_item)
                try:
                    self._log(f"Converted event -> step: {step_item}")
                except Exception:
                    pass
                last_timestamp = event['timestamp']
            
            elif event['type'] == 'mouse_scroll':
                # Convert scroll event to scroll step
                # dy is the scroll amount: positive = up, negative = down
                scroll_amount = event.get('dy', 0)
                
                step_item = {
                    'action': 'scroll',
                    'scroll_amount': scroll_amount,
                    'x': event['x'],
                    'y': event['y'],
                    'delay': delay
                }
                new_steps.append(step_item)
                try:
                    self._log(f"Converted event -> step: {step_item}")
                except Exception:
                    pass
                last_timestamp = event['timestamp']
            
            i += 1
        
        # Add new steps to existing steps
        if new_steps:
            try:
                self._log(f"Appending {len(new_steps)} converted step(s) to macro")
            except Exception:
                pass
        self.steps.extend(new_steps)

    def _save_macro(self):
        """Save macro to file"""
        if not self.steps:
            messagebox.showwarning("Warning", "No steps to save!")
            return
        # Ask user for save location (Save As)
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Macro Files', '*.txt'), ('JSON', '*.json')],
            initialdir=str(self.recordings_folder),
            initialfile='my_macro.txt',
            title='Save Macro As'
        )
        if not path:
            return

        # Ensure image_search steps include image_hash before saving
        for s in self.steps:
            try:
                if s.get('action') == 'image_search':
                    if not s.get('image_hash') and s.get('image_path'):
                        s['image_hash'] = self._compute_image_hash(s['image_path'])
            except Exception:
                pass

        name = Path(path).stem
        with open(path, 'w') as f:
            json.dump({
                'name': name,
                'steps': self.steps
            }, f, indent=2)

        messagebox.showinfo('Success', f'Macro saved to:\n{path}')
        self.status_label.config(text=f'Saved: {Path(path).name}')
    
    def _load_macro(self):
        """Load macro from file"""
        # List available macros
        macro_files = list(self.recordings_folder.glob("*.txt"))
        
        if not macro_files:
            messagebox.showinfo("Info", "No saved macros found!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Macro")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()
        if self.always_on_top:
            dialog.attributes('-topmost', True)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        
        ttk.Label(frame, text="Select Macro:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(list_frame, font=("Arial", 10), height=10, yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        for macro_file in macro_files:
            listbox.insert(tk.END, macro_file.name)
        
        def load():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a macro!")
                return
            
            filename = macro_files[selection[0]]
            
            with open(filename, 'r') as f:
                data = json.load(f)
                steps = data['steps']

            # After loading, reconcile image_search steps by image_hash (match by pixels)
            for s in steps:
                try:
                    if s.get('action') == 'image_search':
                        img_path = s.get('image_path')
                        img_hash = s.get('image_hash')

                        # If image file missing or hash missing, try to compute or find match
                        resolved = None
                        if img_path:
                            p = Path(img_path)
                            if p.exists():
                                # Ensure hash is present
                                if not img_hash:
                                    s['image_hash'] = self._compute_image_hash(p)
                                resolved = p
                        if not resolved and img_hash:
                            found = self._find_image_by_hash(img_hash)
                            if found:
                                s['image_path'] = str(found)
                                s['image_name'] = found.name
                                resolved = found

                except Exception:
                    pass

            self.steps = steps
            
            self._update_steps_display()
            messagebox.showinfo("Success", f"Loaded macro: {data['name']}")
            dialog.destroy()
        
        button_frame = ttk.Frame(frame)
        button_frame.pack()
        
        ttk.Button(button_frame, text="Load", command=load).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)
    
    def _play_macro(self):
        """Play the macro"""
        if not self.steps:
            messagebox.showwarning("Warning", "No steps to play!")
            return
        
        if self.playing:
            messagebox.showinfo("Info", "Macro is already playing!")
            return
        
        # Play in a separate thread
        play_thread = threading.Thread(target=self._execute_macro)
        play_thread.daemon = True
        play_thread.start()
    
    def _execute_macro(self):
        """Execute the macro steps with looping and speed control"""
        self.playing = True
        self.stop_playback = False
        
        # Determine number of loops (0 = infinite)
        loops_remaining = self.loop_count if self.loop_count > 0 else float('inf')
        current_loop = 0
        
        # Track which steps have been executed (for "run once only" steps with step_loop=1)
        # Steps with step_loop=1 only run once per playback session
        executed_once_only_steps = set()
        
        try:
            while loops_remaining > 0 and not self.stop_playback:
                current_loop += 1
                loop_text = f"(Loop {current_loop}" + (f"/{self.loop_count})" if self.loop_count > 0 else "/∞)")
                
                for i, step in enumerate(self.steps, 1):
                    # Check for stop signal
                    if self.stop_playback:
                        self.status_label.config(text="⏹️ Macro stopped by user")
                        return
                    
                    # Get per-step options
                    step_speed = step.get('step_speed', 1.0)
                    step_loop = step.get('step_loop', 1)
                    
                    # Skip "run once only" steps that have already been executed
                    if step_loop == 1 and i in executed_once_only_steps:
                        continue
                    
                    # Mark step as executed if it's a "run once only" step
                    if step_loop == 1:
                        executed_once_only_steps.add(i)
                    
                    # Calculate effective speed (global * step multiplier)
                    effective_speed = self.playback_speed * step_speed
                    
                    # Determine loop count for this step (0 = infinite within this macro loop)
                    if step_loop == 0:
                        step_iterations = float('inf')
                    else:
                        step_iterations = step_loop
                    
                    # Loop this step if needed
                    step_iter_count = 0
                    while step_iter_count < step_iterations:
                        if self.stop_playback:
                            return
                        
                        step_iter_count += 1
                        
                        if step_loop == 0:
                            step_loop_text = f" [∞ iter {step_iter_count}]"
                        elif step_loop > 1:
                            step_loop_text = f" [{step_iter_count}/{step_loop}]"
                        else:
                            step_loop_text = ""
                        
                        self.status_label.config(text=f"▶️ Step {i}/{len(self.steps)}{step_loop_text} {loop_text} @ {effective_speed:.1f}x")
                        
                        action = step['action']
                        delay = step.get('delay', 0.1)
                        
                        # Handle image search step (with wait and timeout)
                        if action == 'image_search':
                            image_path = step.get('image_path', '')
                            confidence = step.get('confidence', 0.8)
                            click_image = step.get('click_image', False)
                            click_mode = step.get('click_mode', 'offset')
                            search_timeout = step.get('search_timeout', 30)  # Default 30 seconds
                            
                            # Wait for image to be found (with timeout)
                            start_time = time.time()
                            result = None
                            search_attempt = 0
                            
                            while result is None and not self.stop_playback:
                                search_attempt += 1
                                elapsed = time.time() - start_time
                                
                                # Check timeout (0 = no timeout, wait forever)
                                if search_timeout > 0 and elapsed >= search_timeout:
                                    # Decide whether to retry or move on based on step setting
                                    on_timeout = step.get('on_timeout', 'move_on')
                                    if on_timeout == 'retry':
                                        # restart the timer and try again
                                        start_time = time.time()
                                        # small pause to avoid tight loop
                                        time.sleep(0.2)
                                        continue
                                    else:
                                        self.status_label.config(text=f"⏱️ Timeout: Image not found after {search_timeout}s")
                                        break
                                
                                # Update status with search progress
                                if search_timeout > 0:
                                    self.status_label.config(text=f"🔍 Searching for image... ({elapsed:.1f}s / {search_timeout}s)")
                                else:
                                    self.status_label.config(text=f"🔍 Searching for image... ({elapsed:.1f}s)")
                                
                                result = self._search_for_image(image_path, confidence)
                                
                                if result is None:
                                    time.sleep(0.2)  # Wait a bit before retrying
                            
                            if result:
                                center_x, center_y, conf = result
                                
                                if click_image:
                                    # Determine click coordinates based on mode
                                    if click_mode == 'absolute' and 'abs_x' in step:
                                        click_x = step['abs_x']
                                        click_y = step['abs_y']
                                    else:
                                        # Offset mode - click relative to image center
                                        offset_x = step.get('offset_x', 0)
                                        offset_y = step.get('offset_y', 0)
                                        click_x = center_x + offset_x
                                        click_y = center_y + offset_y

                                    click_count = step.get('click_count', 1)
                                    for _ in range(int(click_count)):
                                        self.mouse_controller.position = (click_x, click_y)
                                        time.sleep(0.1 / effective_speed)
                                        self.mouse_controller.click(Button.left)
                            # If image not found after timeout, continue to next step
                            # (Status already updated in the search loop)
                        
                        elif action == 'type':
                            # Type text using keyboard controller
                            text_to_type = step.get('text', '')
                            if text_to_type:
                                self.keyboard_controller.type(text_to_type)
                        
                        elif action == 'scroll':
                            # Scroll the mouse wheel
                            scroll_amount = step.get('scroll_amount', 0)
                            
                            # Move to coordinates if specified
                            if 'x' in step and 'y' in step:
                                self.mouse_controller.position = (step['x'], step['y'])
                                time.sleep(0.05 / effective_speed)
                            
                            # Perform the scroll
                            self.mouse_controller.scroll(0, scroll_amount)
                        
                        else:
                            # Regular click/hold step
                            key = step.get('key', '').lower()
                            amount = step.get('amount', 1)
                            
                            # Execute the action
                            if 'click' in key:  # Mouse click
                                button = Button.left if 'left' in key else Button.right
                                
                                # Move to coordinates if specified
                                if 'x' in step and 'y' in step:
                                    self.mouse_controller.position = (step['x'], step['y'])
                                    time.sleep(0.1 / effective_speed)
                                
                                if action == 'click':
                                    for _ in range(int(amount)):
                                        if self.stop_playback:
                                            return
                                        self.mouse_controller.click(button)
                                        time.sleep(0.05 / effective_speed)
                                else:  # hold
                                    self.mouse_controller.press(button)
                                    time.sleep(amount / effective_speed)
                                    self.mouse_controller.release(button)
                            
                            elif key == 'mouse_move':
                                # Just move mouse, no click
                                if 'x' in step and 'y' in step:
                                    self.mouse_controller.position = (step['x'], step['y'])
                            
                            else:  # Keyboard key
                                parsed_key = self._parse_key(key)
                                
                                if parsed_key:
                                    if action == 'click':
                                        for _ in range(int(amount)):
                                            if self.stop_playback:
                                                return
                                            self.keyboard_controller.press(parsed_key)
                                            self.keyboard_controller.release(parsed_key)
                                            time.sleep(0.05 / effective_speed)
                                    else:  # hold
                                        self.keyboard_controller.press(parsed_key)
                                        time.sleep(amount / effective_speed)
                                        self.keyboard_controller.release(parsed_key)
                        
                        # Delay after step (adjusted by effective speed)
                        adjusted_delay = delay / effective_speed
                        time.sleep(adjusted_delay)
                
                # After completing one full macro loop, send a Discord webhook notification if enabled.
                try:
                    self._notify_loop_complete(current_loop)
                except Exception:
                    pass

                loops_remaining -= 1
            
            if not self.stop_playback:
                self.status_label.config(text=f"✅ Macro completed! ({current_loop} loop(s))")
        
        except Exception as e:
            self.status_label.config(text=f"❌ Error: {str(e)}")
            messagebox.showerror("Error", f"Error executing macro:\n{str(e)}")
        
        finally:
            self.playing = False
            self.stop_playback = False
    
    def _parse_key(self, key_str):
        """Parse key string to pynput key"""
        key_map = {
            'enter': Key.enter,
            'space': Key.space,
            'tab': Key.tab,
            'backspace': Key.backspace,
            'delete': Key.delete,
            'esc': Key.esc,
            'escape': Key.esc,
            'shift': Key.shift,
            'ctrl': Key.ctrl,
            'control': Key.ctrl,
            'alt': Key.alt,
            'cmd': Key.cmd,
            'up': Key.up,
            'down': Key.down,
            'left': Key.left,
            'right': Key.right,
            'home': Key.home,
            'end': Key.end,
            'page_up': Key.page_up,
            'pageup': Key.page_up,
            'page_down': Key.page_down,
            'pagedown': Key.page_down,
        }
        
        # Check for function keys
        if key_str.startswith('f') and len(key_str) <= 3:
            try:
                num = int(key_str[1:])
                if 1 <= num <= 12:
                    return getattr(Key, f'f{num}')
            except ValueError:
                pass
        
        return key_map.get(key_str.lower(), key_str if len(key_str) == 1 else None)

    def _is_point_inside_window(self, x, y):
        """Return True if screen coordinate (x,y) is inside the main app window."""
        try:
            wx = int(self.root.winfo_rootx())
            wy = int(self.root.winfo_rooty())
            ww = int(self.root.winfo_width())
            wh = int(self.root.winfo_height())
            if x >= wx and x <= wx + ww and y >= wy and y <= wy + wh:
                return True
        except Exception:
            pass
        return False
    
    def _update_hotkey_buttons(self):
        """Update Play and Record button text with current hotkeys"""
        if hasattr(self, 'play_btn'):
            try:
                self.play_btn.config(text=f"▶️ Play ({self.play_hotkey})")
            except Exception:
                pass
        if hasattr(self, 'record_btn'):
            try:
                self.record_btn.config(text=f"🔴 Record ({self.record_hotkey})")
            except Exception:
                pass
    
    def _toggle_play(self):
        """Toggle play/stop - press once to play, press again to stop"""
        if self.playing:
            self._stop_macro()
        else:
            self._play_macro()
    
    def _toggle_record(self):
        """Toggle record on/off - press once to start, press again to stop"""
        if self.recording:
            self._stop_recording_hotkey()
        else:
            self._start_quick_record()
    
    def _start_quick_record(self):
        """Start recording immediately without dialog"""
        if self.playing:
            messagebox.showinfo("Info", "Cannot record while macro is playing!")
            return
        
        self.root.withdraw()
        time.sleep(0.3)  # Give time to hide window
        
        self.recorded_events = []
        self.record_start_time = time.time()
        self.recording = True
        
        # Use default options: clicks, scroll, keys but not mouse moves
        self.record_options = {
            'mouse_moves': tk.BooleanVar(value=False),
            'clicks': tk.BooleanVar(value=True),
            'scroll': tk.BooleanVar(value=True),
            'keys': tk.BooleanVar(value=True)
        }
        
        # Start listeners
        self.mouse_listener = MouseListener(
            on_click=self._on_record_click,
            on_scroll=self._on_record_scroll
        )
        self.keyboard_listener = KeyboardListener(
            on_press=self._on_record_key_press,
            on_release=self._on_record_key_release
        )
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        
        # Show recording indicator
        self._show_quick_recording_indicator()
    
    def _show_quick_recording_indicator(self):
        """Show recording indicator for quick record"""
        indicator = tk.Toplevel()
        indicator.title("Recording...")
        indicator.geometry("280x80")
        indicator.attributes('-topmost', True)
        indicator.overrideredirect(True)
        
        screen_width = indicator.winfo_screenwidth()
        indicator.geometry(f"+{screen_width - 300}+20")
        
        frame = tk.Frame(indicator, bg="#e74c3c", padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        
        tk.Label(frame, text="🔴 RECORDING", font=("Arial", 12, "bold"), 
                bg="#e74c3c", fg="white").pack()
        tk.Label(frame, text=f"Press {self.record_hotkey} to stop", font=("Arial", 10), 
                bg="#e74c3c", fg="white").pack()
        
        self.recording_indicator = indicator
        self.parent_dialog = None
        
        def check_stop():
            if self.recording:
                indicator.after(100, check_stop)
            else:
                indicator.destroy()
                self._stop_recording()
        
        indicator.after(100, check_stop)

    def _toggle_quickrec(self):
        """Toggle the QuickRec recorder (start/stop)."""
        if self.quickrec_active:
            self._stop_quickrec()
        else:
            self._start_quickrec()

    def _start_quickrec(self):
        if self.playing:
            messagebox.showinfo("Info", "Cannot record while macro is playing!")
            return

        # remember previous topmost state and set window on top for QuickRec
        try:
            self._prev_topmost = bool(self.root.attributes("-topmost"))
        except Exception:
            self._prev_topmost = False
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        self.quickrec_active = True
        self.recorded_events = []
        self.record_start_time = time.time()
        self.recording = True

        # Default QuickRec options: no mouse moves (keeps steps compact)
        self.record_options = {
            'mouse_moves': tk.BooleanVar(value=False),
            'clicks': tk.BooleanVar(value=True),
            'scroll': tk.BooleanVar(value=True),
            'keys': tk.BooleanVar(value=True)
        }

        # Start listeners using existing handlers
        self.mouse_listener = MouseListener(
            on_click=self._on_record_click,
            on_move=self._on_record_move if self.record_options['mouse_moves'].get() else None,
            on_scroll=self._on_record_scroll if self.record_options['scroll'].get() else None
        )
        self.keyboard_listener = KeyboardListener(
            on_press=self._on_record_key_press,
            on_release=self._on_record_key_release
        )

        self.mouse_listener.start()
        self.keyboard_listener.start()

        self.quickrec_btn.config(text="⏹️ Stop QuickRec")
        self.status_label.config(text="🔴 QuickRec recording...")

    def _stop_quickrec(self):
        self.quickrec_active = False
        self.recording = False
        try:
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
        except Exception:
            pass

        self.quickrec_btn.config(text="🎥 QuickRec")
        self.status_label.config(text="Ready")

        # restore previous topmost state
        try:
            if hasattr(self, '_prev_topmost'):
                self.root.attributes("-topmost", self._prev_topmost)
                del self._prev_topmost
        except Exception:
            pass

        # Convert recorded events to steps and append
        if getattr(self, 'recorded_events', None):
            self._convert_events_to_steps()
            self._update_steps_display()

    # (TinyRec removed) QuickRec uses existing recording handlers and converters
    
    def _stop_recording_hotkey(self):
        """Stop recording when triggered by hotkey"""
        self.recording = False
        # Stop recording listeners immediately
        try:
            if self.mouse_listener:
                self.mouse_listener.stop()
                self.mouse_listener = None
            if self.keyboard_listener:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
        except Exception:
            pass
        # Instantly stop and clean up indicator if present
        try:
            if hasattr(self, 'recording_indicator') and self.recording_indicator.winfo_exists():
                self.recording_indicator.destroy()
            self._stop_recording()
        except Exception:
            self._stop_recording()
    
    def _start_hotkey_listener(self):
        """Start the global hotkey listener"""
        def on_press(key):
            try:
                # Get the key name
                if hasattr(key, 'name'):
                    key_name = key.name.upper()
                elif hasattr(key, 'char') and key.char:
                    key_name = key.char.upper()
                else:
                    return

                # Play hotkey toggles play/stop regardless of state
                if key_name == self.play_hotkey.upper():
                    self.root.after(0, self._toggle_play)

                # Record hotkey toggles record/stop regardless of state
                elif key_name == self.record_hotkey.upper():
                    self.root.after(0, self._toggle_record)
            except Exception:
                pass
        
        self.hotkey_listener = KeyboardListener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()
    
    def run(self):
        """Run the GUI application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    app = SimpleMacroGUI()
    app.run()

if __name__ == "__main__":
    main()
