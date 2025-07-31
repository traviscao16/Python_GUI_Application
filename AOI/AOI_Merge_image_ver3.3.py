import os
from PIL import Image, ImageDraw, ImageFont, ImageFile
from memory_profiler import profile
import pandas as pd

# Increase the decompression bomb limit
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

folder_path = r"C:\Users\zbrzyy\Desktop\Logcheck\dummyNewClipRun2\L2"

def get_image_files(folder_path):
    return [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

@profile
def get_strip_name_and_type(filename):
    parts = filename.split('-')
    if len(parts) < 4:
        raise ValueError(f"Filename format is incorrect: {filename}")
    strip_name = parts[-4]
    image_type = parts[-2]
    return strip_name, image_type

def get_label_from_filename(filename):
    patterns_labels = {
        "R01C01": "U1",
        "R01C02": "U2",
        "R01C03": "U3",
        "R01C04": "U4",
        "R01C05": "U5",
        "R01C06": "U6",
        "R01C07": "U7",
        "R01C08": "U8",
        "R01C09": "U9",
        "R01C10": "U10",
    }
    for pattern, label in patterns_labels.items():
        if pattern in filename:
            return label
    return ""

def rotate_image(image_path):
    with Image.open(image_path) as im:
        rotated = im.rotate(-90, expand=True)  # Rotate the image to the right
    return rotated

def draw_text(image, text, position, font_size=200):
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", font_size)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x, y = position
    draw.text((x - text_width // 2, y), text, font=font, fill="white")

def merge_images(images_dict):
    merged_images = {}
    for strip_name, images in images_dict.items():
        total_width = max(sum(img['image'].width for img in images['L1']), sum(img['image'].width for img in images['L2']))
        max_height_L1 = max(img['image'].height for img in images['L1']) if images['L1'] else 0
        max_height_L2 = max(img['image'].height for img in images['L2']) if images['L2'] else 0
        
        merged_img = Image.new('L', (total_width, max_height_L1 + max_height_L2))
        
        x_offset = 0
        for img in images['L1']:
            image = img['image'].convert('L') if img['image'].mode != 'L' else img['image']
            merged_img.paste(image, (x_offset, 0))
            label = get_label_from_filename(img['filename'])
            if label:
                draw_text(merged_img, label, (x_offset + image.width // 2, 10))
            x_offset += image.width
        
        x_offset = 0
        for img in images['L2']:
            image = img['image'].convert('L') if img['image'].mode != 'L' else img['image']
            merged_img.paste(image, (x_offset, max_height_L1))
            x_offset += image.width
        
        # Add a margin of 10 pixels from the left and bottom edges for the strip name label
        margin = 5
        draw_text(merged_img, strip_name, (margin, max_height_L1 + max_height_L2 - margin))
        merged_images[strip_name] = merged_img
    return merged_images

def save_and_resize_merged_images(merged_images, folder_path, resize_percentage):
    output_folder = os.path.join(folder_path, "merge_result")
    os.makedirs(output_folder, exist_ok=True)
    for strip_name, merged_img in merged_images.items():
        # Resize the merged image
        new_width = int(merged_img.width * resize_percentage / 100)
        new_height = int(merged_img.height * resize_percentage / 100)
        resized_img = merged_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save the resized image
        output_filename = strip_name + "_merged.jpg"
        output_path = os.path.join(output_folder, output_filename)
        resized_img.save(output_path, 'JPEG', quality=75, dpi=(75, 75))
        print(f"Resized and merged image for strip {strip_name} saved as {output_filename}")



image_files = get_image_files(folder_path)
images_dict = {}
for image_file in image_files:
    try:
        strip_name, image_type = get_strip_name_and_type(image_file)
    except ValueError as e:
        print(e)
        continue
    if strip_name not in images_dict:
        images_dict[strip_name] = {'L1': [], 'L2': []}
    if image_type not in images_dict[strip_name]:
        images_dict[strip_name][image_type] = []
    image_path = os.path.join(folder_path, image_file)
    rotated_image = rotate_image(image_path)
    images_dict[strip_name][image_type].append({'image': rotated_image, 'filename': image_file})

merged_images = merge_images(images_dict)
save_and_resize_merged_images(merged_images, folder_path, 50)
