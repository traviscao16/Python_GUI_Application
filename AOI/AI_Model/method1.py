import cv2
import numpy as np
import matplotlib.pyplot as plt

def find_and_draw_largest_contour(image_path):
    # Load the image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image at {image_path}")
        return
    
    # Convert to grayscale and apply a threshold
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
    
    # Find all contours in the binary image
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"Found a total of {len(contours)} contours in the image.")
    
    # Find the largest contour
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Create a blank image to draw the contour on
        contour_image = np.zeros_like(image)
        cv2.drawContours(contour_image, [largest_contour], -1, (0, 255, 0), 2)
        
        plt.figure(figsize=(8, 6))
        plt.imshow(cv2.cvtColor(contour_image, cv2.COLOR_BGR2RGB))
        plt.title('Largest Contour Detected')
        plt.show()
        
        return largest_contour
    else:
        print("No contours were found.")
        return None

# The result of this step is the largest_contour variable.
# It is a NumPy array containing all the points of the contour.
largest_contour = find_and_draw_largest_contour('good1.jpg')

def get_contour_coordinates(contour):
    """
    Extracts and prints the coordinates of a given contour.
    
    Args:
        contour (np.ndarray): A single contour returned by cv2.findContours.
    """
    if contour is None:
        return
        
    # The contour is a NumPy array.
    print(f"\nThe contour has {len(contour)} points.")
    print("Here are the coordinates of the first 5 points:")
    
    # Method 1: Loop through the array
    for i, point in enumerate(contour[:5]):
        x, y = point[0]
        print(f"  Point {i+1}: (x={x}, y={y})")
        
    # Method 2: Reshape the array for easier access
    all_coordinates = contour.reshape(-1, 2)
    print("\nHere are the first 5 points from a simplified array:")
    print(all_coordinates[:5])

# Now, we combine the two steps:
if __name__ == "__main__":
    largest_contour = find_and_draw_largest_contour('good1.jpg')
    if largest_contour is not None:
        get_contour_coordinates(largest_contour)