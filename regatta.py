import tkinter as tk
from tkinter import messagebox, ttk, filedialog, simpledialog
import serial
import serial.tools.list_ports
import time
import os
from datetime import datetime
from threading import Thread
import json

NUM_ROWS = 8
NUM_COLS = 30

class PortSelector:
    def __init__(self):
        self.selected_port = None

        dialog = tk.Tk()
        dialog.title("COM Port Auswahl")

        ports = [p.device for p in serial.tools.list_ports.comports()]

        label = tk.Label(dialog, text="Wählen Sie den COM Port:")
        label.pack(pady=5)

        port_var = tk.StringVar()
        port_combo = ttk.Combobox(dialog, textvariable=port_var, values=ports)
        port_combo.pack(pady=5)

        if ports:
            port_combo.set(ports[0])
        else:
            port_combo.set("KEINE PORTS")
            messagebox.showwarning("Warnung", "Keine COM Ports gefunden! Programm startet im Test-Modus.")

        def on_select():
            self.selected_port = port_var.get() if port_var.get() != "KEINE PORTS" else None
            dialog.destroy()

        tk.Button(dialog, text="OK", command=on_select).pack(pady=5)
        dialog.mainloop()

class LEDMatrixApp:
    def __init__(self, root, port_selector):
        # Auto-scan variables at the start
        self.auto_scan_active = False
        self.last_processed_file = None
        self.watch_path = None
        self.scan_interval = 15
        self.templates_file = "led_templates.json"

        # Animation variables
        self.animation_frames = []
        self.animation_running = False
        self.animation_delay = 500  # ms per frame (default)
        self.animation_index = 0
        self.animation_mode = "LOOP"  # or "ONCE"
        self.animation_fps = 2  # default FPS
        self.fps_slider = None  # <-- add this line

        # Basic initialization
        self.root = root
        self.root.title("LED-Matrix Editor")
        self.root.configure(bg='black')

        # Colors
        self.led_off_color = '#1a1a1a'
        self.led_on_color = '#ffbf00'
        self.text_color = '#ffbf00'
        self.defective_color = '#400000'

        # Create status label early
        self.status_label = tk.Label(root, text="", fg=self.text_color, bg='black')

        # Create grid and buttons
        self.entries = [[None for _ in range(NUM_COLS)] for _ in range(NUM_ROWS)]
        self.create_grid()
        self.entries[0][0].config(state='normal')

        # Create buttons
        self.send_button = tk.Button(root, text="An Tafel senden", command=self.send_data)
        self.send_button.grid(row=NUM_ROWS + 1, column=0, columnspan=NUM_COLS, pady=10)

        self.clear_button = tk.Button(root, text="Zurücksetzen", command=self.clear_grid)
        self.clear_button.grid(row=NUM_ROWS + 1, column=NUM_COLS//2, columnspan=NUM_COLS//2, pady=10)

        # Now create menu and style everything
        self.create_menu()

        # Mode tracking
        self.current_mode = "manual"  # modes: manual, race_results

        port = port_selector.selected_port
        try:
            self.ser = serial.Serial(
                port=port, baudrate=38400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.run_initialization_test()
        except serial.SerialException as e:
            messagebox.showerror("Serieller Fehler", str(e))
            self.ser = None

        self.valid_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789äöüÄÖÜ .,!?|-:+*/\()=#%<>')
        self.replacement_char = '?'

        self.send_button.configure(
            bg=self.led_off_color,
            fg=self.text_color,
            activebackground=self.led_on_color,
            activeforeground='black'
        )

        self.clear_button.configure(
            bg=self.led_off_color,
            fg=self.text_color,
            activebackground=self.led_on_color,
            activeforeground='black'
        )

        # Load saved templates
        self.load_templates()

        # Position status label last
        self.status_label.grid(row=NUM_ROWS + 2, column=0, columnspan=NUM_COLS, pady=5)

    def create_menu(self):
        menubar = tk.Menu(self.root, bg=self.led_off_color, fg=self.text_color)
        self.root.config(menu=menubar)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.led_off_color, fg=self.text_color,
                           activebackground=self.led_on_color, activeforeground='black')
        menubar.add_cascade(label="Datei", menu=file_menu)
        file_menu.add_command(label="Rennergebnisse laden", command=self.load_race_results)
        file_menu.add_command(label="Animation laden", command=self.load_animation)
        
        # Templates submenu
        templates_menu = tk.Menu(file_menu, tearoff=0, bg=self.led_off_color, fg=self.text_color)
        file_menu.add_cascade(label="Vorlagen", menu=templates_menu)
        templates_menu.add_command(label="Aktuelle Anzeige speichern", command=self.save_template)
        templates_menu.add_command(label="Vorlage laden", command=self.load_template)
        
        # Auto-scan submenu
        auto_menu = tk.Menu(file_menu, tearoff=0, bg=self.led_off_color, fg=self.text_color)
        file_menu.add_cascade(label="Auto-Scan", menu=auto_menu)
        auto_menu.add_command(label="Verzeichnis wählen", command=self.select_watch_path)
        auto_menu.add_command(label="Start Auto-Scan", command=self.start_auto_scan)
        auto_menu.add_command(label="Stop Auto-Scan", command=self.stop_auto_scan)
        
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.root.quit)
        
        # Mode Menu
        mode_menu = tk.Menu(menubar, tearoff=0, bg=self.led_off_color, fg=self.text_color,
                           activebackground=self.led_on_color, activeforeground='black')
        menubar.add_cascade(label="Modus", menu=mode_menu)
        mode_menu.add_command(label="Manueller Modus", command=self.set_manual_mode)
        mode_menu.add_command(label="Rennergebnisse", command=self.set_race_mode)

    def load_templates(self):
        self.templates = {}
        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, 'r') as f:
                    self.templates = json.load(f)
            except:
                pass

    def save_template(self):
        name = tk.simpledialog.askstring("Speichern", "Name der Vorlage:")
        if name:
            content = []
            for row in range(NUM_ROWS):
                line = ''.join(self.entries[row][col].get() or ' ' for col in range(NUM_COLS))
                content.append(line)
            self.templates[name] = content
            with open(self.templates_file, 'w') as f:
                json.dump(self.templates, f)

    def load_template(self):
        if not self.templates:
            messagebox.showinfo("Info", "Keine Vorlagen verfügbar")
            return
        
        name = tk.simpledialog.askstring("Laden", "Name der Vorlage:",
                                       initialvalue=list(self.templates.keys())[0])
        if name and name in self.templates:
            self.clear_grid()
            content = self.templates[name]
            for row, line in enumerate(content):
                for col, char in enumerate(line):
                    self.entries[row][col].insert(0, char)
            self.send_data()

    def select_watch_path(self):
        path = filedialog.askdirectory(title="Verzeichnis für Auto-Scan wählen")
        if path:
            self.watch_path = path
            messagebox.showinfo("Info", f"Überwache Verzeichnis: {path}")

    def show_status(self, message, duration=3000):
        """Show status message and clear after duration ms"""
        self.status_label.config(text=message)
        self.root.after(duration, lambda: self.status_label.config(text=""))

    def start_auto_scan(self):
        if not self.watch_path:
            messagebox.showerror("Fehler", "Bitte zuerst ein Verzeichnis wählen")
            return
        
        self.auto_scan_active = True
        self.last_processed_file = None
        self.last_modified_time = 0
        Thread(target=self.auto_scan_thread, daemon=True).start()
        self.show_status(f"Auto-Scan aktiv: {self.watch_path}")

    def stop_auto_scan(self):
        self.auto_scan_active = False
        self.show_status("Auto-Scan gestoppt")

    def auto_scan_thread(self):
        while self.auto_scan_active:
            try:
                files = [(f, os.path.getmtime(os.path.join(self.watch_path, f))) 
                        for f in os.listdir(self.watch_path) 
                        if f.endswith('.txt')]
                
                if files:
                    newest_file, mod_time = max(files, key=lambda x: x[1])
                    full_path = os.path.join(self.watch_path, newest_file)
                    
                    if mod_time > self.last_modified_time + 0.1:
                        self.last_modified_time = mod_time
                        time.sleep(0.5)
                        self.root.after(0, self._safe_load_file, full_path)
            except Exception as e:
                self.show_status(f"Scan-Fehler: {str(e)}")
            
            time.sleep(1)

    def _safe_load_file(self, filepath):
        try:
            self.load_race_results(filepath)
            self.show_status("Neue Daten geladen")
        except Exception as e:
            self.show_status(f"Ladefehler: {str(e)}")

    def load_race_results(self, filename=None):
        if not filename:
            filename = filedialog.askopenfilename(
                filetypes=[("Text files", "*.txt"), ("All files", "*")]
            )
        if not filename:
            return
            
        # Try different encodings
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        lines = None
        
        for encoding in encodings:
            try:
                with open(filename, 'r', encoding=encoding) as file:
                    lines = file.readlines()
                break  # If successful, exit the loop
            except UnicodeDecodeError:
                continue
        
        if not lines:
            self.show_status("Fehler beim Lesen der Datei")
            return
        
        # Simply replace first line with Sommerregatta 2025
        if lines:
            lines[0] = "Sommerregatta 2025".ljust(NUM_COLS) + "\n"

        # --- NEW: Temporarily set all entries to normal for update ---
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.entries[row][col].config(state='normal')
        # ------------------------------------------------------------

        self.clear_grid()
        # Display file content in grid and highlight filled cells
        self.root.update_idletasks()  # Single update at start
        for row, line in enumerate(lines[:NUM_ROWS]):
            line = line.rstrip()
            for col, char in enumerate(line[:NUM_COLS]):
                self.entries[row][col].delete(0, tk.END)
                if char not in self.valid_chars:
                    char = self.replacement_char
                bg = self.defective_color if self.is_defective(row, col) else self.led_off_color
                self.entries[row][col].configure(bg=bg, fg=self.text_color, readonlybackground=bg)
                self.entries[row][col].insert(0, char)
        self.root.update()  # Single update at end

        # --- NEW: Set entries to readonly if in race mode ---
        if self.current_mode == "race_results":
            for row in range(NUM_ROWS):
                for col in range(NUM_COLS):
                    self.entries[row][col].config(state='readonly')
        # ----------------------------------------------------

        self.set_race_mode()
        self.send_data()

    def load_animation(self):
        filename = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*")],
            title="Animationsdatei wählen"
        )
        if not filename:
            return
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            frames, mode, fps = self.parse_animation_frames(content)
            if not frames:
                self.show_status("Keine Frames gefunden")
                return
            self.animation_frames = frames
            self.animation_index = 0
            self.animation_running = True
            self.animation_mode = mode
            self.animation_fps = fps
            self.animation_delay = int(1000 / self.animation_fps)
            self.set_animation_mode()
            self.show_status(f"Animation gestartet ({len(frames)} Frames, {mode}, {fps} FPS)")
            self.play_animation()
        except Exception as e:
            self.show_status(f"Fehler beim Laden: {e}")

    def parse_animation_frames(self, content):
        frames = []
        current = []
        mode = "LOOP"
        fps = 2
        for line in content.splitlines():
            if line.strip().startswith("#MODE:"):
                mode = line.strip().split(":", 1)[1].strip().upper()
            elif line.strip().startswith("#FPS:"):
                try:
                    fps = max(1, int(line.strip().split(":", 1)[1].strip()))
                except Exception:
                    fps = 2
            elif line.strip().startswith("FRAME"):
                current = []
            elif line.strip() == "==":
                if len(current) == NUM_ROWS:
                    frames.append(current)
                current = []
            else:
                if len(current) < NUM_ROWS:
                    current.append(line.ljust(NUM_COLS)[:NUM_COLS])
        if len(current) == NUM_ROWS:
            frames.append(current)
        return frames, mode, fps

    def play_animation(self):
        if not self.animation_running or not self.animation_frames:
            return
        frame = self.animation_frames[self.animation_index]
        self.display_animation_frame(frame)
        # Show frame number in status
        self.show_status(f"Frame {self.animation_index+1}/{len(self.animation_frames)}", duration=500)
        self.animation_index += 1
        if self.animation_index >= len(self.animation_frames):
            if self.animation_mode == "ONCE":
                self.animation_running = False
                self.show_status("Animation beendet")
                return
            else:
                self.animation_index = 0
        self.root.after(self.animation_delay, self.play_animation)

    def set_animation_mode(self):
        self.current_mode = "animation"
        # Add stop button if not present
        if not hasattr(self, "stop_animation_button"):
            self.stop_animation_button = tk.Button(self.root, text="Animation stoppen", command=self.stop_animation)
            self.stop_animation_button.configure(
                bg=self.led_off_color,
                fg=self.text_color,
                activebackground=self.led_on_color,
                activeforeground='black'
            )
            self.stop_animation_button.grid(row=NUM_ROWS + 3, column=0, columnspan=NUM_COLS, pady=5)
        else:
            self.stop_animation_button.grid(row=NUM_ROWS + 3, column=0, columnspan=NUM_COLS, pady=5)
        # --- FPS Slider ---
        if not self.fps_slider:
            self.fps_slider = tk.Scale(self.root, from_=1, to=10, orient=tk.HORIZONTAL,
                                       label="FPS", bg=self.led_off_color, fg=self.text_color,
                                       troughcolor=self.led_on_color, highlightbackground='black',
                                       command=self.on_fps_change)
            self.fps_slider.set(self.animation_fps)
            self.fps_slider.grid(row=NUM_ROWS + 4, column=0, columnspan=NUM_COLS, pady=5)
        else:
            self.fps_slider.set(self.animation_fps)
            self.fps_slider.grid(row=NUM_ROWS + 4, column=0, columnspan=NUM_COLS, pady=5)
        # Make grid readonly
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.entries[row][col].config(state='readonly')

    def on_fps_change(self, val):
        try:
            fps = int(val)
            self.animation_fps = fps
            self.animation_delay = int(1000 / max(1, fps))
        except Exception:
            pass

    def stop_animation(self):
        self.animation_running = False
        if hasattr(self, "stop_animation_button"):
            self.stop_animation_button.grid_remove()
        if self.fps_slider:
            self.fps_slider.grid_remove()
        self.show_status("Animation gestoppt")
        self.set_manual_mode()

    def display_animation_frame(self, frame):
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.entries[row][col].config(state='normal')
        for row, line in enumerate(frame):
            for col, char in enumerate(line):
                self.entries[row][col].delete(0, tk.END)
                if char not in self.valid_chars:
                    char = self.replacement_char
                bg = self.defective_color if self.is_defective(row, col) else self.led_off_color
                self.entries[row][col].configure(bg=bg, fg=self.text_color, readonlybackground=bg)
                self.entries[row][col].insert(0, char)
        self.send_data()
        if self.current_mode == "animation":
            for row in range(NUM_ROWS):
                for col in range(NUM_COLS):
                    self.entries[row][col].config(state='readonly')

    def set_manual_mode(self):
        self.current_mode = "manual"
        self.animation_running = False
        if hasattr(self, "stop_animation_button"):
            self.stop_animation_button.grid_remove()
        if self.fps_slider:
            self.fps_slider.grid_remove()
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                bg = self.defective_color if self.is_defective(row, col) else self.led_off_color
                self.entries[row][col].config(state='normal')
                self.entries[row][col].configure(bg=bg, fg=self.text_color, readonlybackground=bg)

    def set_race_mode(self):
        self.current_mode = "race_results"
        self.animation_running = False
        if hasattr(self, "stop_animation_button"):
            self.stop_animation_button.grid_remove()
        if self.fps_slider:
            self.fps_slider.grid_remove()
        # Make all entries read-only
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                bg = self.defective_color if self.is_defective(row, col) else self.led_off_color
                self.entries[row][col].config(state='readonly')
                self.entries[row][col].configure(bg=bg, fg=self.text_color, readonlybackground=bg)

    def create_grid(self):
        # Create frame for grid with padding
        grid_frame = tk.Frame(self.root, padx=10, pady=10, bg='black')
        grid_frame.grid(row=0, column=0)
        
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                bg_color = self.defective_color if self.is_defective(row, col) else self.led_off_color
                entry = tk.Entry(grid_frame, width=2, justify="center",
                               font=('Courier', 10, 'bold'),
                               fg=self.text_color,
                               bg=bg_color,
                               insertbackground=self.text_color,
                               highlightbackground='black',
                               highlightthickness=1)
                entry.grid(row=row, column=col, padx=1, pady=1)
                entry.bind("<KeyRelease>", lambda e, r=row, c=col: self.on_key(e, r, c))
                entry.bind("<Left>", lambda e, r=row, c=col: self.navigate("left", r, c))
                entry.bind("<Right>", lambda e, r=row, c=col: self.navigate("right", r, c))
                entry.bind("<Up>", lambda e, r=row, c=col: self.navigate("up", r, c))
                entry.bind("<Down>", lambda e, r=row, c=col: self.navigate("down", r, c))
                entry.bind("<BackSpace>", lambda e, r=row, c=col: self.handle_backspace(e, r, c))
                entry.bind("<Home>", lambda e, r=row: self.shift_line_left(r))
                entry.bind("<End>", lambda e, r=row, c=col: self.shift_right_of_cursor_left(r, c))
                self.entries[row][col] = entry

    def is_defective(self, row, col):
        # First line except last 4, last line except last 5
        return (row == 0 and col < NUM_COLS - 4) or (row == NUM_ROWS - 1 and col < NUM_COLS - 5)

    def navigate(self, direction, current_row, current_col):
        next_row, next_col = current_row, current_col
        
        if direction == "left":
            next_col = max(0, current_col - 1)
        elif direction == "right":
            next_col = min(NUM_COLS - 1, current_col + 1)
        elif direction == "up":
            next_row = max(0, current_row - 1)
        elif direction == "down":
            next_row = min(NUM_ROWS - 1, current_row + 1)
            
        self.entries[next_row][next_col].focus()
        return "break"  # Prevents default behavior

    def handle_backspace(self, event, row, col):
        # Clear current cell
        self.entries[row][col].delete(0, tk.END)
        
        if col > 0:  # Not at start of line
            prev_col = col - 1
            self.entries[row][prev_col].focus()
        elif row > 0:  # At start of line and not first line
            prev_row = row - 1
            self.entries[prev_row][NUM_COLS-1].focus()
        return "break"

    def shift_line_left(self, row):
        """Shift all characters in the line to the left, fill rightmost with space."""
        for col in range(NUM_COLS - 1):
            val = self.entries[row][col + 1].get()
            self.entries[row][col].delete(0, tk.END)
            self.entries[row][col].insert(0, val)
        self.entries[row][NUM_COLS - 1].delete(0, tk.END)
        self.entries[row][NUM_COLS - 1].insert(0, ' ')
        return "break"

    def shift_right_of_cursor_left(self, row, col):
        """Shift all characters right of the cursor to the left, fill last with space."""
        for i in range(col, NUM_COLS - 1):
            val = self.entries[row][i + 1].get()
            self.entries[row][i].delete(0, tk.END)
            self.entries[row][i].insert(0, val)
        self.entries[row][NUM_COLS - 1].delete(0, tk.END)
        self.entries[row][NUM_COLS - 1].insert(0, ' ')
        return "break"

    def on_key(self, event, row, col):
        value = self.entries[row][col].get()
        
        # Handle navigation and special keys
        if event.keysym in ['Left', 'Right', 'Up', 'Down', 'BackSpace']:
            return
        if event.keysym == 'Home':
            self.shift_line_left(row)
            return "break"
        if event.keysym == 'End':
            self.shift_right_of_cursor_left(row, col)
            return "break"
            
        if value and value[-1] not in self.valid_chars:
            # Replace invalid character with ?
            self.entries[row][col].delete(0, tk.END)
            self.entries[row][col].insert(0, self.replacement_char)
            value = self.replacement_char

        if len(value) > 1:
            self.entries[row][col].delete(1, tk.END)

        if value:
            bg = self.defective_color if self.is_defective(row, col) else self.led_off_color
            self.entries[row][col].configure(bg=bg, fg=self.text_color, readonlybackground=bg)
            next_row, next_col = row, col + 1
            if next_col >= NUM_COLS:
                # Zeile voll → mit Leerzeichen auffüllen
                for i in range(NUM_COLS):
                    if not self.entries[row][i].get():
                        self.entries[row][i].insert(0, ' ')
                next_row += 1
                next_col = 0

            if next_row < NUM_ROWS:
                self.entries[next_row][next_col].focus()
                self.entries[next_row][next_col].config(state='normal')

    def clear_grid(self):
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                bg = self.defective_color if self.is_defective(row, col) else self.led_off_color
                self.entries[row][col].delete(0, tk.END)
                self.entries[row][col].configure(bg=bg, fg=self.text_color, readonlybackground=bg)
                self.root.update()
        # ...existing code...

    def send_brightness_command(self):
        if not self.ser:
            return
        try:
            msg = bytearray([0x01, 0xFF, 0x03])
            self.ser.write(msg)
            self.ser.flush()
        except serial.SerialException as e:
            self.show_status(f"Helligkeits-Fehler: {str(e)}")

    def send_data(self):
        if not self.ser:
            if self.current_mode == "manual":
                self.show_status("Test-Modus: Daten würden gesendet werden")
            return

        try:
            all_text = b''
            for row_idx in range(NUM_ROWS):
                text = ''.join(self.entries[row_idx][col].get() or ' ' for col in range(NUM_COLS))
                text = text[:NUM_COLS].ljust(NUM_COLS)
                all_text += text.encode('iso-8859-1', errors='replace')
            msg = bytearray()
            msg.append(0x01)
            msg.append(0xFF)
            msg.extend(all_text)
            self.ser.write(msg)
            self.ser.flush()
            self.show_status("Daten gesendet")
        except serial.SerialException as e:
            self.show_status(f"Sende-Fehler: {str(e)}")

    def run_initialization_test(self):
        original_mode = self.current_mode
        self.current_mode = "initialization"
        try:
            self.clear_grid()
            for row in range(NUM_ROWS):
                for col in range(NUM_COLS):
                    self.entries[row][col].insert(0, '0')
            self.send_data()
            time.sleep(5)
            for row in range(NUM_ROWS):
                for col in range(NUM_COLS):
                    self.entries[row][col].delete(0, tk.END)
                    self.entries[row][col].insert(0, '1')
            self.send_data()
            time.sleep(5)
            self.clear_grid()
            self.send_data()
        finally:
            self.current_mode = original_mode

    def on_closing(self):
        self.root.destroy()

if __name__ == "__main__":
    port_selector = PortSelector()
    root = tk.Tk()
    app = LEDMatrixApp(root, port_selector)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
