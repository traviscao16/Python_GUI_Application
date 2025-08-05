import cv2
import numpy as np
import matplotlib.pyplot as plt
import os

def template_matching_analysis(good_image_path, test_image_path, template_coords, tolerance=5):
    """
    Performs template matching to detect horizontal displacement for a single image.
    
    Args:
        good_image_path (str): Path to the reference "good" image.
        test_image_path (str): Path to the image to be tested.
        template_coords (tuple): (x, y, w, h) defining the template region in the good image.
        tolerance (int): The maximum allowed difference in pixel position for alignment.
    """
    
    # --- Load images and extract template ---
    good_img = cv2.imread(good_image_path, cv2.IMREAD_GRAYSCALE)
    test_img = cv2.imread(test_image_path, cv2.IMREAD_GRAYSCALE)
    
    if good_img is None or test_img is None:
        print(f"Error: Could not load images for analysis. Check paths.")
        return

    x, y, w, h = template_coords
    template = good_img[y:y+h, x:x+w]
    
    # --- Perform template matching on the test image ---
    result = cv2.matchTemplate(test_img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    top_left = max_loc
    bottom_right = (top_left[0] + w, top_left[1] + h)

    # --- Compare positions ---
    original_x = x
    matched_x = top_left[0]
    
    displacement = abs(original_x - matched_x)
    
    # --- Visualize the result ---
    color_img = cv2.cvtColor(test_img, cv2.COLOR_GRAY2BGR)
    # Draw original location in good image (green box)
    cv2.rectangle(color_img, (original_x, y), (original_x + w, y + h), (0, 255, 0), 2)
    # Draw the matched location in the test image (red box)
    cv2.rectangle(color_img, top_left, bottom_right, (0, 0, 255), 2)
    
    plt.imshow(cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB))
    plt.title(f"Analysis of {os.path.basename(test_image_path)} (Displacement: {displacement} pixels)")
    plt.show()

    # --- Check for misalignment ---
    if displacement > tolerance:
        print(f"RESULT for {os.path.basename(test_image_path)}: MISALIGNED. Displacement of {displacement} pixels exceeds tolerance of {tolerance}.")
    else:
        print(f"RESULT for {os.path.basename(test_image_path)}: ALIGNED. Displacement of {displacement} pixels is within tolerance.")

# --- MAIN SCRIPT ---
if __name__ == "__main__":
    # --- Setup your paths and template ---
    good_image_path = r"E:\Python_Coding\Python_GUI_Application-1\AOI\AI_Model\dataset\train\good1.jpg"
    test_folder_path = r'E:\Python_Coding\Python_GUI_Application-1\AOI\AI_Model\dataset\test'  # IMPORTANT: Change this to your folder path
    
    # To find the template coordinates, you can manually inspect the image.
    # The template is the part of the component that looks like an "H"
    # (top-left x, top-left y, width, height)
    template_region = (370, 480, 200, 100) 
    
    # Create the test folder if it doesn't exist
    if not os.path.exists(test_folder_path):
        os.makedirs(test_folder_path)
        print(f"Created folder: '{test_folder_path}'. Please add your test images here.")
    else:
        # Loop through all files in the test folder
        for filename in os.listdir(test_folder_path):
            # Check if the file is an image (you can add more extensions if needed)
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_test_path = os.path.join(test_folder_path, filename)
                print(f"\n--- Analyzing file: {filename} ---")
                # Call the analysis function for each image
                template_matching_analysis(good_image_path, full_test_path, template_region, tolerance=5)