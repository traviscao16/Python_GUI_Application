import cv2
import numpy as np

# Load the image
image_path = r"C:\Users\zbrzyy\Desktop\Logcheck\VT28A0R7\test 2.jpg"  # Replace with your actual image file path
image = cv2.imread(image_path)

# Validate image loading
if image is None:
    raise ValueError("Image could not be loaded. Check the file path.")

# Define custom x-coordinate range for the search zone
x_start = 550   # Adjust this value
x_end = 850    # Adjust this value

# Extract the custom search zone
custom_zone = image[:, x_start:x_end]

# Convert to grayscale
gray = cv2.cvtColor(custom_zone, cv2.COLOR_BGR2GRAY)

# Apply adaptive thresholding
adaptive_thresh = cv2.adaptiveThreshold(
    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY_INV, 11, 2
)

# Apply morphological operations to reduce noise
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
morph = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_OPEN, kernel, iterations=2)

# Find contours
contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Filter vertical contours
height = custom_zone.shape[0]
vertical_contours = []
for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    aspect_ratio = h / float(w) if w > 0 else 0
    area = cv2.contourArea(cnt)
    if h > 30 and aspect_ratio > 2.5 and area > 100:
        vertical_contours.append(cnt)

# Draw contours and center lines
annotated = custom_zone.copy()
for cnt in vertical_contours:
    x, y, w, h = cv2.boundingRect(cnt)
    cx = x + w // 2
    cv2.drawContours(annotated, [cnt], -1, (0, 255, 0), 2)
    cv2.line(annotated, (cx, 0), (cx, height), (255, 0, 0), 1)

# Resize images for display
def resize_image(img, max_width=200):
    scale_ratio = max_width / img.shape[1]
    new_height = int(img.shape[0] * scale_ratio)
    return cv2.resize(img, (max_width, new_height))

resized_thresh = resize_image(adaptive_thresh)
resized_morph = resize_image(morph)
resized_annotated = resize_image(annotated)

# Show all stages
cv2.imshow("Stage 1 - Adaptive Threshold", resized_thresh)
cv2.imshow("Stage 2 - Morphological Cleaning", resized_morph)
cv2.imshow("Stage 3 - Annotated Result", resized_annotated)

# Save results
cv2.imwrite("custom_zone_adaptive_threshold.png", resized_thresh)
cv2.imwrite("custom_zone_morph_cleaned.png", resized_morph)
cv2.imwrite("custom_zone_annotated.png", resized_annotated)

cv2.waitKey(0)
cv2.destroyAllWindows()
