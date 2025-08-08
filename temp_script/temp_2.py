import os
import pandas as pd

# 🔧 Change this to your local folder path
folder_path = r'\\Saigon\osv\Operations\public_folder\VY NGUYEN\Merge\New folder'

# Output file path
merged_csv_path = os.path.join(folder_path, 'merged_output_with_headers.csv')

# Check if folder exists
if not os.path.exists(folder_path):
    print(f"❌ Folder path does not exist: {folder_path}")
else:
    with open(merged_csv_path, 'w', encoding='utf-8', newline='') as outfile:
        for filename in os.listdir(folder_path):
            if filename.endswith('.xlsx'):
                file_path = os.path.join(folder_path, filename)
                print(f"📄 Processing: {filename}")
                try:
                    xls = pd.ExcelFile(file_path, engine='openpyxl')
                    print(f"   ➕ Sheets found: {xls.sheet_names}")

                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet_name, engine='openpyxl')

                        if df.empty:
                            print(f"   ⚠️ Skipping empty sheet: {sheet_name}")
                            continue

                        # Save individual CSV file for each sheet
                        csv_filename = f"{filename.replace('.xlsx', '')}_{sheet_name}.csv"
                        csv_path = os.path.join(folder_path, csv_filename)
                        df.to_csv(csv_path, index=False)

                        # Write to merged file
                        outfile.write(f'--- Start of {filename} | Sheet: {sheet_name} ---\n')
                        df.to_csv(outfile, index=False)
                        outfile.write(f'\n--- End of {filename} | Sheet: {sheet_name} ---\n\n')

                except Exception as e:
                    print(f"❌ Failed to process {filename}: {e}")

    print(f"✅ All files and sheets converted and merged into: {merged_csv_path}")
