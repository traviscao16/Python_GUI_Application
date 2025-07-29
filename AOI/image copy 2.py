import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np

class DistanceMeasurerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Distance Measurer")

        self.canvas = tk.Canvas(root, cursor="cross", bg="gray")
        self.canvas.pack(fill="both", expand=True)

        self.scale_label = tk.Label(root, text="Scale (mm/pixel):")
        self.scale_label.pack(side="left")
        self.scale_entry = tk.Entry(root)
        self.scale_entry.insert(0, "0.00625")
        self.scale_entry.pack(side="left")

        self.load_button = tk.Button(root, text="Load Image", command=self.load_image)
        self.load_button.pack(side="left")

        self.mode_button = tk.Button(root, text="Switch to X-Axis", command=self.toggle_mode)
        self.mode_button.pack(side="left")

        self.result_label = tk.Label(root, text="Distance: ")
        self.result_label.pack(side="left")

        self.image = None
        self.original_image = None
        self.tk_image = None
        self.line_ids = []
        self.line_positions = [100, 200]

        self.zoom_factor = 1.0
        self.mode = 'Y'

        self.canvas.bind("<B1-Motion>", self.move_line)
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<Button-4>", self.zoom)
        self.canvas.bind("<Button-5>", self.zoom)

        self.canvas_width = self.root.winfo_screenwidth()
        self.canvas_height = self.root.winfo_screenheight()

    def load_image(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.original_image = cv2.cvtColor(cv2.imread(file_path), cv2.COLOR_BGR2RGB)
            self.resize_image_to_screen()
            self.zoom_factor = 1.0
            self.display_image()

    def resize_image_to_screen(self):
        if self.original_image is not None:
            img_h, img_w = self.original_image.shape[:2]
            scale_w = self.canvas_width / img_w
            scale_h = self.canvas_height / img_h
            scale = min(scale_w, scale_h)
            new_size = (int(img_w * scale), int(img_h * scale))
            self.image = cv2.resize(self.original_image, new_size, interpolation=cv2.INTER_AREA)

    def display_image(self):
        if self.image is not None:
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
                x_zoomed = int(pos * self.zoom_factor)
                line_id = self.canvas.create_line(x_zoomed, 0, x_zoomed, height, fill="red", width=2)
            else:
                y_zoomed = int(pos * self.zoom_factor)
                line_id = self.canvas.create_line(0, y_zoomed, width, y_zoomed, fill="red", width=2)
            self.line_ids.append(line_id)
        self.calculate_distance()

    def move_line(self, event):
        for i, line_id in enumerate(self.line_ids):
            coords = self.canvas.coords(line_id)
            if self.mode == 'Y' and abs(event.x - coords[0]) < 10:
                self.line_positions[i] = int(event.x / self.zoom_factor)
                self.draw_lines()
                break
            elif self.mode == 'X' and abs(event.y - coords[1]) < 10:
                self.line_positions[i] = int(event.y / self.zoom_factor)
                self.draw_lines()
                break

    def calculate_distance(self):
        if len(self.line_positions) == 2:
            pixel_distance = abs(self.line_positions[1] - self.line_positions[0])
            try:
                scale = float(self.scale_entry.get())
                distance_mm = pixel_distance * scale
                axis = "Y" if self.mode == 'Y' else "X"
                self.result_label.config(text=f"{axis}-Axis Distance: {distance_mm:.4f} mm")
            except ValueError:
                self.result_label.config(text="Invalid scale")

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
