import cv2
import numpy as np
import matplotlib.pyplot as plt

def find_corners_of_square(image_path):
    """
    Loads an image, finds the largest contour, and detects its four corners.
    
    Args:
        image_path (str): The path to the image file.
    """
    # 1. Load the image and find the outer frame contour
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image at {image_path}")
        return
        
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort contours by area to get the largest one (the outer frame)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    if len(contours) > 0:
        outer_frame_contour = contours[0]
        
        # 2. Approximate the contour to find the corners
        
        # Get the perimeter of the contour
        perimeter = cv2.arcLength(outer_frame_contour, True)
        
        # Set a small epsilon for approximation (e.g., 2% of the perimeter)
        epsilon = 0.02 * perimeter
        
        # Find the simplified polygon with fewer vertices
        approx_corners = cv2.approxPolyDP(outer_frame_contour, epsilon, True)
        
        # 3. Visualize the result
        
        # Create a copy of the image to draw on
        image_with_corners = image.copy()
        
        # Draw the original contour in red
        cv2.drawContours(image_with_corners, [outer_frame_contour], -1, (0, 0, 255), 3)
        
        # Draw circles at each detected corner in green
        for point in approx_corners:
            x, y = point[0]
            cv2.circle(image_with_corners, (x, y), 8, (0, 255, 0), -1)
            
        plt.figure(figsize=(10, 8))
        plt.imshow(cv2.cvtColor(image_with_corners, cv2.COLOR_BGR2RGB))
        plt.title(f"Detected Corners in {image_path}")
        plt.show()

        print(f"Found a total of {len(approx_corners)} corners on the outer frame.")
        if len(approx_corners) == 4:
            print("Successfully detected all four corners.")
            print("Corner Coordinates:")
            for i, point in enumerate(approx_corners):
                print(f"  Corner {i+1}: ({point[0][0]}, {point[0][1]})")
        else:
            print(f"Warning: Expected 4 corners but found {len(approx_corners)}. Try adjusting the epsilon value.")
    else:
        print("Could not find any contours in the image.")

# Run the function on your image
find_corners_of_square('good1.jpg')