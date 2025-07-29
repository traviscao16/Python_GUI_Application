import cv2
import numpy as np
import os
import shutil

def template_matching(input_image_path, template_image_path, threshold=0.5):
    # Read the input image and template image
    input_image = cv2.imread(input_image_path)
    template_image = cv2.imread(template_image_path)

    # Convert the images to grayscale
    input_gray = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)

    # Perform template matching
    result = cv2.matchTemplate(input_gray, template_gray, cv2.TM_CCOEFF_NORMED)

    # Check if the pattern is detected based on the threshold
    loc = np.where(result >= threshold)
    return len(loc[0]) > 0

def sort_images(input_folder, template_folder, output_base_folder, threshold=0.5):
    # Iterate over all files in the input folder
    for filename in os.listdir(input_folder):
        input_image_path = os.path.join(input_folder, filename)
        
        # Check if the file is an image
        if os.path.isfile(input_image_path) and filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Iterate over all template images in the template folder
            for template_filename in os.listdir(template_folder):
                template_image_path = os.path.join(template_folder, template_filename)
                
                # Perform template matching
                if template_matching(input_image_path, template_image_path, threshold):
                    # Create an output folder for each template image
                    output_folder = os.path.join(output_base_folder, os.path.splitext(template_filename)[0])
                    if not os.path.exists(output_folder):
                        os.makedirs(output_folder)
                    
                    # Move the image to the output folder if pattern is detected
                    shutil.move(input_image_path, os.path.join(output_folder, filename))
                    break

# Example usage
input_folder = r'C:\Users\zbrzyy\Desktop\Logcheck\Clip 4 - DOE solder for clip thruhole\Image'
template_folder = r"C:\Users\zbrzyy\Desktop\Works\CLIP\Clip_Sorting_template"
output_base_folder = input_folder

sort_images(input_folder, template_folder, output_base_folder)

# Print a success message
print("Images sorted and moved to the respective output folders based on the template images.")
