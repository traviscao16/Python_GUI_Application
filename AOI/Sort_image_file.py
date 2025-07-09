import os
import shutil

# Define the source directory
source_dir = r'C:\Users\zbrzyy\Desktop\Logcheck\VT26A0W3'

# Define the target directories inside the source directory
target_dir_L1 = os.path.join(source_dir, 'L1')
target_dir_L2 = os.path.join(source_dir, 'L2')

# Create target directories if they don't exist
os.makedirs(target_dir_L1, exist_ok=True)
os.makedirs(target_dir_L2, exist_ok=True)

# Iterate over files in the source directory
for filename in os.listdir(source_dir):
    if 'L1' in filename and filename.endswith('.jpg'):
        shutil.move(os.path.join(source_dir, filename), os.path.join(target_dir_L1, filename))
    elif 'L2' in filename and filename.endswith('.jpg'):
        shutil.move(os.path.join(source_dir, filename), os.path.join(target_dir_L2, filename))

print("Files have been sorted and moved successfully.")