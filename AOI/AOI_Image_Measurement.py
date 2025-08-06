# Full code with lower and upper tolerance limits for X and Y axes

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import cv2

class DistanceMeasurerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Distance Measurer")
        
        # Set full screen mode
        self.root.state('zoomed')  # For Windows
        # Alternative for other systems: self.root.attributes('-fullscreen', True)
        
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.canvas = tk.Canvas(root, cursor="cross", bg="gray")
        self.canvas.pack(fill="both", expand=True)
        # Remove conflicting bindings - we'll handle them conditionally
        self.dragging = False  # Add this attribute

        control_frame = tk.Frame(root)
        control_frame.pack(fill="x")

        self.scale_label = tk.Label(control_frame, text="Scale (mm/pixel):")
        self.scale_label.pack(side="left")
        self.scale_entry = tk.Entry(control_frame, width=10)
        self.scale_entry.insert(0, "0.00625")
        self.scale_entry.pack(side="left")

        self.load_button = tk.Button(control_frame, text="Load Image", command=self.load_image)
        self.load_button.pack(side="left")

        self.mode_button = tk.Button(control_frame, text="Switch to X-Axis", command=self.toggle_mode)
        self.mode_button.pack(side="left")

        # Add Zoom In and Zoom Out buttons
        self.zoom_in_button = tk.Button(control_frame, text="Zoom In", command=self.zoom_in)
        self.zoom_in_button.pack(side="left")
        self.zoom_out_button = tk.Button(control_frame, text="Zoom Out", command=self.zoom_out)
        self.zoom_out_button.pack(side="left")

        self.result_label = tk.Label(control_frame, text="Distance: ")
        self.result_label.pack(side="left")

        # Tolerance inputs
        self.tol_x_label = tk.Label(control_frame, text="X Tol (mm):")
        self.tol_x_label.pack(side="left")
        self.tol_x_lower = tk.Entry(control_frame, width=5)
        self.tol_x_lower.insert(0, "0.05")
        self.tol_x_lower.pack(side="left")
        self.tol_x_upper = tk.Entry(control_frame, width=5)
        self.tol_x_upper.insert(0, "0.85")
        self.tol_x_upper.pack(side="left")

        self.tol_y_label = tk.Label(control_frame, text="Y Tol (mm):")
        self.tol_y_label.pack(side="left")
        self.tol_y_lower = tk.Entry(control_frame, width=5)
        self.tol_y_lower.insert(0, "0.92")
        self.tol_y_lower.pack(side="left")
        self.tol_y_upper = tk.Entry(control_frame, width=5)
        self.tol_y_upper.insert(0, "2.52")
        self.tol_y_upper.pack(side="left")

        self.image = None
        self.original_image = None
        self.tk_image = None
        self.line_ids = []
        self.line_positions = [100, 200]
        self.zoom_factor = 1.0
        self.mode = 'Y'
        self.selected_line = 0
        self.file_name = ""  # Add this line
        self.pan_start = None
        self.pan_offset = [0, 0]
        
        # Variables for maintaining scale accuracy (kept for compatibility)
        self.original_image_width = None
        self.original_image_height = None
        self.display_scale_factor = 1.0  # No scaling applied - kept for compatibility
        self.canvas.bind("<ButtonPress-3>", self.start_pan)
        self.canvas.bind("<B3-Motion>", self.do_pan)
        self.canvas.bind("<ButtonRelease-3>", self.end_pan)

        # Remove mouse wheel and button zoom bindings
        # self.canvas.bind("<MouseWheel>", self.zoom)
        # self.canvas.bind("<Button-4>", self.zoom)
        # self.canvas.bind("<Button-5>", self.zoom)
        self.root.bind("<Left>", self.move_left)
        self.root.bind("<Right>", self.move_right)
        self.root.bind("<Up>", self.move_up)
        self.root.bind("<Down>", self.move_down)
        self.root.bind("<Escape>", self.exit_fullscreen)

        self.calib_button = tk.Button(control_frame, text="Calibration", command=self.open_calibration_window)
        self.calib_button.pack(side="left")
        
    def exit_fullscreen(self, event=None):
        """Exit full screen mode"""
        self.root.state('normal')

        # Calibration state
        self.calibration_mode = False
        self.calib_zone_start = None
        self.calib_zone_rect = None
        self.calib_measured_label = None

        # Calibration circle variables
        self.calib_circle = None
        self.calib_circle_label = None
        self.calib_circle_center = None
        self.calib_circle_radius = None
        self.calib_drag_mode = None  # "move" or "resize"
        self.calib_drag_offset = None
        
        # Initialize event bindings
        self.bind_events()

    def bind_events(self):
        """Bind events based on current mode"""
        # Unbind all mouse events first
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<ButtonPress-2>")
        self.canvas.unbind("<B2-Motion>")
        self.canvas.unbind("<ButtonRelease-2>")
        
        if self.calibration_mode:
            # Bind calibration events
            self.canvas.bind("<ButtonPress-2>", self.calib_circle_start_event)
            self.canvas.bind("<B2-Motion>", self.calib_circle_draw_event)
            self.canvas.bind("<ButtonRelease-2>", self.calib_circle_end_event)
            self.canvas.bind("<ButtonPress-1>", self.calib_circle_select_event)
            self.canvas.bind("<B1-Motion>", self.calib_circle_adjust_event)
            self.canvas.bind("<ButtonRelease-1>", self.calib_circle_release_event)
        else:
            # Bind line selection and dragging events
            self.canvas.bind("<Button-1>", self.select_line)
            self.canvas.bind("<B1-Motion>", self.drag_line)

    def load_image(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.file_name = file_path.split("/")[-1] if "/" in file_path else file_path.split("\\")[-1]  # Store just the file name
            # Load image with proper error handling
            loaded_image = cv2.imread(file_path)
            if loaded_image is None:
                messagebox.showerror("Error", "Failed to load image")
                return
            self.original_image = cv2.cvtColor(loaded_image, cv2.COLOR_BGR2RGB)
            
            # Store original dimensions
            self.original_image_height, self.original_image_width = self.original_image.shape[:2]
            
            # Keep original image size - no auto-resize
            self.image = self.original_image.copy()
            self.display_scale_factor = 1.0  # No scaling applied
            
            self.zoom_factor = 1.0
            self.calibration_mode = False  # Ensure not in calibration mode
            self.canvas.delete("calib_circle")
            self.canvas.delete("calib_circle_label")
            self.bind_events()  # Rebind events
            self.display_image()



    def start_pan(self, event):
        self.pan_start = (event.x, event.y)

    def do_pan(self, event):
        if self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.pan_offset[0] += dx
            self.pan_offset[1] += dy
            self.pan_start = (event.x, event.y)
            self.display_image()

    def end_pan(self, event):
        self.pan_start = None

    def display_image(self):
        if self.image is None:
            return
        img = Image.fromarray(self.image)
        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(self.pan_offset[0], self.pan_offset[1], anchor="nw", image=self.tk_image, tags="IMG")
        # Show file name in bottom right (adjust for pan)
        if self.file_name:
            width = self.image.shape[1]
            height = self.image.shape[0]
            self.canvas.create_text(width - 10 + self.pan_offset[0], height - 10 + self.pan_offset[1], text=self.file_name, anchor="se", fill="white", font=("Arial", 10, "bold"), tags="file_name")
        self.draw_lines()

    def draw_lines(self):
        if self.image is None:
            return
        for line_id in self.line_ids:
            self.canvas.delete(line_id)
        self.line_ids.clear()
        height, width = self.image.shape[:2]
        for i, pos in enumerate(self.line_positions):
            if i == self.selected_line:
                line_color = "blue"
                line_width = 1.5
            else:
                line_color = "red"
                line_width = 1.5
            if self.mode == 'Y':
                x = int(pos * self.zoom_factor) + self.pan_offset[0]
                line_id = self.canvas.create_line(x, self.pan_offset[1], x, height + self.pan_offset[1], fill=line_color, width=line_width)
            else:
                y = int(pos * self.zoom_factor) + self.pan_offset[1]
                line_id = self.canvas.create_line(self.pan_offset[0], y, width + self.pan_offset[0], y, fill=line_color, width=line_width)
            self.line_ids.append(line_id)
        self.calculate_distance()

    def select_line(self, event):
        # Detect if mouse is near a line and select it (no drag yet)
        for i, line_id in enumerate(self.line_ids):
            coords = self.canvas.coords(line_id)
            if self.mode == 'Y' and abs(event.x - coords[0]) < 5:
                self.selected_line = i
                self.dragging = False  # Only select, don't drag yet
                self.draw_lines()
                break
            elif self.mode == 'X' and abs(event.y - coords[1]) < 5:
                self.selected_line = i
                self.dragging = False
                self.draw_lines()
                break

    def drag_line(self, event):
        # Start dragging only if mouse is near the selected line
        if self.selected_line is not None:
            self.dragging = True
        if not self.dragging:
            return
        if self.mode == 'Y':
            self.line_positions[self.selected_line] = int((event.x - self.pan_offset[0]) / self.zoom_factor)
        else:
            self.line_positions[self.selected_line] = int((event.y - self.pan_offset[1]) / self.zoom_factor)
        self.draw_lines()

    def move_left(self, event):
        if self.mode == 'Y':
            self.line_positions[self.selected_line] -= 1
            self.draw_lines()

    def move_right(self, event):
        if self.mode == 'Y':
            self.line_positions[self.selected_line] += 1
            self.draw_lines()

    def move_up(self, event):
        if self.mode == 'X':
            self.line_positions[self.selected_line] -= 1
            self.draw_lines()

    def move_down(self, event):
        if self.mode == 'X':
            self.line_positions[self.selected_line] += 1
            self.draw_lines()

    def calculate_distance(self):
        if len(self.line_positions) == 2:
            pixel_distance = abs(self.line_positions[1] - self.line_positions[0])
            try:
                scale = float(self.scale_entry.get())
                distance_mm = pixel_distance * scale
                axis = "Y" if self.mode == 'Y' else "X"
                self.result_label.config(text=f"{axis}-Axis Distance: {distance_mm:.4f} mm")

                # Get tolerance values
                if self.mode == 'Y':
                    tol_lower = float(self.tol_y_lower.get())
                    tol_upper = float(self.tol_y_upper.get())
                else:
                    tol_lower = float(self.tol_x_lower.get())
                    tol_upper = float(self.tol_x_upper.get())

                # Determine tolerance status
                if tol_lower <= distance_mm <= tol_upper:
                    status = "OK"
                    color = "green"
                else:
                    status = "Out of Tolerance"
                    color = "red"

                # Create combined text: "1.9 mm - OK" or "1.9 mm - Out of Tolerance"
                combined_text = f"{distance_mm:.3f} mm - {status}"

                # Remove old text elements
                self.canvas.delete("distance_text")
                self.canvas.delete("tolerance_status")

                # Position at bottom center of image, aligned with filename
                if self.image is not None:
                    width = self.image.shape[1]
                    height = self.image.shape[0]
                    center_x = width / 2 + self.pan_offset[0]
                    bottom_y = height - 10 + self.pan_offset[1]
                    
                    self.canvas.create_text(center_x, bottom_y, text=combined_text, fill=color, font=("Arial", 10, "bold"), anchor="s", tags="distance_text")

            except ValueError:
                self.result_label.config(text="Invalid scale or tolerance")

    def toggle_mode(self):
        self.mode = 'X' if self.mode == 'Y' else 'Y'
        self.mode_button.config(text=f"Switch to {'Y' if self.mode == 'X' else 'X'}-Axis")
        self.line_positions = [100, 200]
        self.draw_lines()

    # Add new zoom methods
    def zoom_in(self):
        if self.original_image is None:
            return
        self.zoom_factor *= 1.1
        self.zoom_factor = min(self.zoom_factor, 10)
        new_size = (int(self.original_image.shape[1] * self.zoom_factor),
                    int(self.original_image.shape[0] * self.zoom_factor))
        self.image = cv2.resize(self.original_image, new_size, interpolation=cv2.INTER_LINEAR)
        self.pan_offset = [0, 0]  # Reset pan on zoom
        self.display_image()

    def zoom_out(self):
        if self.original_image is None:
            return
        self.zoom_factor /= 1.2
        self.zoom_factor = max(self.zoom_factor, 0.1)
        new_size = (int(self.original_image.shape[1] * self.zoom_factor),
                    int(self.original_image.shape[0] * self.zoom_factor))
        self.image = cv2.resize(self.original_image, new_size, interpolation=cv2.INTER_LINEAR)
        self.pan_offset = [0, 0]  # Reset pan on zoom
        self.display_image()

    def open_calibration_window(self):
        calib_win = tk.Toplevel(self.root)
        calib_win.title("Calibration")
        tk.Label(calib_win, text="Hole Diameter (mm):").grid(row=0, column=0)
        hole_dia_entry = tk.Entry(calib_win)
        hole_dia_entry.insert(0, "2.9")
        hole_dia_entry.grid(row=0, column=1)

        tk.Label(calib_win, text="Current Measured Diameter (pixels):").grid(row=1, column=0)
        measured_label = tk.Label(calib_win, text="0")
        measured_label.grid(row=1, column=1)

        def draw_zone():
            self.calibration_mode = True
            self.calib_measured_label = measured_label
            self.bind_events()  # Rebind events for calibration mode
            calib_win.lift()
            calib_win.focus_force()

        tk.Button(calib_win, text="Draw Search Zone", command=draw_zone).grid(row=2, column=0, columnspan=2)

        def apply_calibration():
            try:
                hole_dia = float(hole_dia_entry.get())
                measured = float(measured_label["text"])
                if measured > 0:
                    scale = hole_dia / measured
                    self.scale_entry.delete(0, tk.END)
                    self.scale_entry.insert(0, f"{scale:.6f}")
                    self.calibration_mode = False  # Ensure exit calibration mode
                    self.canvas.delete("calib_circle")
                    self.canvas.delete("calib_circle_label")
                    self.bind_events()  # Rebind events for normal mode
                    calib_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(calib_win, text="Apply Calibration", command=apply_calibration).grid(row=3, column=0, columnspan=2)

        def on_close():
            self.calibration_mode = False  # Ensure exit calibration mode
            self.canvas.delete("calib_circle")
            self.canvas.delete("calib_circle_label")
            self.bind_events()  # Rebind events for normal mode
            calib_win.destroy()

        calib_win.protocol("WM_DELETE_WINDOW", on_close)

    def calib_circle_start_event(self, event):
        if self.calibration_mode:
            self.canvas.delete("calib_circle")
            self.canvas.delete("calib_circle_label")
            self.calib_circle_center = (event.x, event.y)
            self.calib_circle_radius = 1
            self.calib_circle = self.canvas.create_oval(
                event.x, event.y, event.x, event.y,
                outline="yellow", width=2, tags="calib_circle"
            )

    def calib_circle_draw_event(self, event):
        if self.calibration_mode and self.calib_circle_center and self.calib_circle is not None:
            x0, y0 = self.calib_circle_center
            r = ((event.x - x0) ** 2 + (event.y - y0) ** 2) ** 0.5
            self.calib_circle_radius = r
            self.canvas.coords(
                self.calib_circle,
                x0 - r, y0 - r, x0 + r, y0 + r
            )
            self._update_calib_circle_label()

    def calib_circle_end_event(self, event):
        if self.calibration_mode and self.calib_circle_center:
            self._update_calib_circle_label()
            # Remain in calibration mode for adjustment

    def calib_circle_select_event(self, event):
        # Allow move or resize if click near center or edge
        if self.calib_circle_center and self.calib_circle_radius:
            x0, y0 = self.calib_circle_center
            r = self.calib_circle_radius
            dist = ((event.x - x0) ** 2 + (event.y - y0) ** 2) ** 0.5
            if abs(dist - r) < 10:
                self.calib_drag_mode = "resize"
            elif dist < r:
                self.calib_drag_mode = "move"
                self.calib_drag_offset = (event.x - x0, event.y - y0)
            else:
                self.calib_drag_mode = None

    def calib_circle_adjust_event(self, event):
        if self.calib_drag_mode == "move" and self.calib_drag_offset is not None:
            dx, dy = self.calib_drag_offset
            self.calib_circle_center = (event.x - dx, event.y - dy)
            x0, y0 = self.calib_circle_center
            r = self.calib_circle_radius
            if self.calib_circle is not None:
                self.canvas.coords(
                    self.calib_circle,
                    x0 - r, y0 - r, x0 + r, y0 + r
                )
            self._update_calib_circle_label()
        elif self.calib_drag_mode == "resize" and self.calib_circle_center is not None:
            x0, y0 = self.calib_circle_center
            r = ((event.x - x0) ** 2 + (event.y - y0) ** 2) ** 0.5
            self.calib_circle_radius = r
            if self.calib_circle is not None:
                self.canvas.coords(
                    self.calib_circle,
                    x0 - r, y0 - r, x0 + r, y0 + r
                )
            self._update_calib_circle_label()

    def calib_circle_release_event(self, event):
        self.calib_drag_mode = None
        self.calib_drag_offset = None

    def _update_calib_circle_label(self):
        self.canvas.delete("calib_circle_label")
        if not (self.calib_circle_center is not None and self.calib_circle_radius is not None):
            return
        x0, y0 = self.calib_circle_center
        r = self.calib_circle_radius
        # Convert to image coordinates
        x_img = (x0 - self.pan_offset[0]) / self.zoom_factor
        y_img = (y0 - self.pan_offset[1]) / self.zoom_factor
        r_img = r / self.zoom_factor
        diameter_px = r_img * 2
        try:
            scale = float(self.scale_entry.get())
            diameter_mm = diameter_px * scale
        except Exception:
            diameter_mm = 0.0
        # Show diameter in pixels in calibration window
        if self.calib_measured_label:
            self.calib_measured_label.config(text=f"{diameter_px:.2f}")
        # Show diameter in mm on canvas
        self.calib_circle_label = self.canvas.create_text(
            x0, y0 + r + 20,
            text=f"{diameter_mm:.3f} mm",
            fill="yellow", font=("Arial", 12, "bold"), tags="calib_circle_label"
        )

# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = DistanceMeasurerApp(root)
    root.mainloop()
