import cv2
import numpy as np
from tensorflow.keras.models import load_model
import os

def is_centered(img_path, model, threshold=0.85, center_margin=0.2):
    """Check if main object is centered"""
    # Load and preprocess image
    img = cv2.imread(img_path)
    img = cv2.resize(img, (256, 256))
    img = img / 255.0
    img = np.expand_dims(img, axis=0)
    
    # Get prediction
    pred = model.predict(img)[0][0]
    
    # Computer vision check (complementary to the model)
    gray = cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # Get largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Calculate center of object
        obj_center_x = x + w/2
        obj_center_y = y + h/2
        
        # Image center
        img_center_x = gray.shape[1] / 2
        img_center_y = gray.shape[0] / 2
        
        # Calculate distance from center
        dist_x = abs(obj_center_x - img_center_x) / img_center_x
        dist_y = abs(obj_center_y - img_center_y) / img_center_y
        
        # Combined check (model prediction + position verification)
        return (pred > threshold) and (dist_x < center_margin) and (dist_y < center_margin)
    return pred > threshold

# Load model
model = load_model('centering_model.h5')

# Test single image
#result = is_centered('test/NG.jpg', model)
#print("Image is:", "GOOD" if result else "BAD")

# For batch processing
def process_folder(folder_path):
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            img_path = os.path.join(folder_path, filename)
            result = is_centered(img_path, model)
            print(f"{filename}: {'GOOD' if result else 'BAD'}")

# Example usage
process_folder(r'E:\Python_Coding\Python_GUI_Application-1\AOI\AI_Model\dataset\test')