# Full code with lower and upper tolerance limits for X and Y axes

import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import cv2

class DistanceMeasurerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Distance Measurer")

        self.canvas = tk.Canvas(root, cursor="cross", bg="gray")
        self.canvas.pack(fill="both", expand=True)

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

        self.canvas.bind("<B1-Motion>", self.move_line)
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<Button-4>", self.zoom)
        self.canvas.bind("<Button-5>", self.zoom)
        self.root.bind("<Left>", self.move_left)
        self.root.bind("<Right>", self.move_right)
        self.root.bind("<Up>", self.move_up)
        self.root.bind("<Down>", self.move_down)

    def load_image(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.original_image = cv2.cvtColor(cv2.imread(file_path), cv2.COLOR_BGR2RGB)
            self.resize_image_to_screen()
            self.zoom_factor = 1.0
            self.display_image()

    def resize_image_to_screen(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        img_h, img_w = self.original_image.shape[:2]
        scale = min(screen_w / img_w, screen_h / img_h)
        new_size = (int(img_w * scale), int(img_h * scale))
        self.image = cv2.resize(self.original_image, new_size, interpolation=cv2.INTER_AREA)

    def display_image(self):
        img = Image.fromarray(self.image)
        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image, tags="IMG")
        self.draw_lines()

    def draw_lines(self):
        for line_id in self.line_ids:
            self.canvas.delete(line_id)
        self.line_ids.clear()
        height, width = self.image.shape[:2]
        for pos in self.line_positions:
            if self.mode == 'Y':
                x = int(pos * self.zoom_factor)
                line_id = self.canvas.create_line(x, 0, x, height, fill="red", width=2)
            else:
                y = int(pos * self.zoom_factor)
                line_id = self.canvas.create_line(0, y, width, y, fill="red", width=2)
            self.line_ids.append(line_id)
        self.calculate_distance()

    def move_line(self, event):
        for i, line_id in enumerate(self.line_ids):
            coords = self.canvas.coords(line_id)
            if self.mode == 'Y' and abs(event.x - coords[0]) < 10:
                self.selected_line = i
                self.line_positions[i] = int(event.x / self.zoom_factor)
                self.draw_lines()
                break
            elif self.mode == 'X' and abs(event.y - coords[1]) < 10:
                self.selected_line = i
                self.line_positions[i] = int(event.y / self.zoom_factor)
                self.draw_lines()
                break

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

                self.canvas.delete("distance_text")
                if self.mode == 'Y':
                    mid_x = int(sum(self.line_positions) / 2 * self.zoom_factor)
                    self.canvas.create_text(mid_x, 20, text=f"{distance_mm:.4f} mm", fill="yellow", font=("Arial", 14), tags="distance_text")
                    tol_lower = float(self.tol_y_lower.get())
                    tol_upper = float(self.tol_y_upper.get())
                else:
                    mid_y = int(sum(self.line_positions) / 2 * self.zoom_factor)
                    self.canvas.create_text(60, mid_y, text=f"{distance_mm:.4f} mm", fill="yellow", font=("Arial", 14), tags="distance_text")
                    tol_lower = float(self.tol_x_lower.get())
                    tol_upper = float(self.tol_x_upper.get())

                self.canvas.delete("tolerance_status")
                if tol_lower <= distance_mm <= tol_upper:
                    status = "OK"
                    color = "green"
                else:
                    status = "Out of Tolerance"
                    color = "red"
                self.canvas.create_text(100, 40, text=status, fill=color, font=("Arial", 12), tags="tolerance_status")

            except ValueError:
                self.result_label.config(text="Invalid scale or tolerance")

    def toggle_mode(self):
        self.mode = 'X' if self.mode == 'Y' else 'Y'
        self.mode_button.config(text=f"Switch to {'Y' if self.mode == 'X' else 'X'}-Axis")
        self.line_positions = [100, 200]
        self.draw_lines()

    def zoom(self, event):
        if self.original_image is None:
            return
        if event.delta > 0 or event.num == 4:
            self.zoom_factor *= 1.1
        elif event.delta < 0 or event.num == 5:
            self.zoom_factor /= 1.1
        self.zoom_factor = max(0.1, min(self.zoom_factor, 10))
        new_size = (int(self.original_image.shape[1] * self.zoom_factor),
                    int(self.original_image.shape[0] * self.zoom_factor))
        self.image = cv2.resize(self.original_image, new_size, interpolation=cv2.INTER_LINEAR)
        self.display_image()

# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = DistanceMeasurerApp(root)
    root.mainloop()
