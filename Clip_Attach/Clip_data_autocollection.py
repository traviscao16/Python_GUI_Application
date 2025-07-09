import csv
from datetime import datetime
import os

# Define the log file name with the updated path
log_file_name = r"C:\Users\zbrzyy\Desktop\CLIP\Logfile_monitor\WW46\Clip6\Module 4 SiC.log"
output_folder = r"C:\Users\zbrzyy\Desktop\CLIP\Logfile_monitor\WW46\Clip6\data"

# Define the Machine ID manually
machine_id = "CLip6"

def read_log_file(file_path):
    with open(file_path, 'r') as log_file:
        lines = log_file.readlines()
    return lines

def get_workweek(date_str):
    date = datetime.strptime(date_str, "%d-%m-%Y")
    workweek = int(date.strftime("%U"))
    return str(workweek + 1)

def process_data(lines):
    header = lines[0].strip().split(';')
    data_rows = [line.strip().split(';') for line in lines[1:]]
    header = ['Date', 'Time', 'Workweek', 'Time_Start_Lot', 'MachineID'] + header[1:4] + ['OffsetX', 'OffsetY', 'OffsetT', 'UnitLocation', 'StripMapID_Count', 'Strip_Status']
    
    first_startlot_dict = {}
    stripmapid_count_dict = {}
    updated_data_rows = []
    
    for row in data_rows:
        if len(row) == 5 and row[2].strip():  # Ensure the row has the correct number of columns and LotID is not blank
            timestamp = row[0]
            try:
                date, time = timestamp.split()
                date = datetime.strptime(date, "%d.%m.%Y").strftime("%d-%m-%Y")
                time = datetime.strptime(time, "%H:%M:%S.%f").strftime("%H:%M:%S")
                offset_measurements = row[4]
                offsets = offset_measurements.split()
                offset_x = offsets[2]
                offset_y = offsets[5]
                offset_t = offsets[8]
                lot_id = row[2]
                strip_id = row[3]
                
                if lot_id not in first_startlot_dict:
                    first_startlot_dict[lot_id] = f"{date} {time}"
                first_startlot = first_startlot_dict[lot_id]
                
                if strip_id not in stripmapid_count_dict:
                    stripmapid_count_dict[strip_id] = 0
                stripmapid_count_dict[strip_id] += 1
                
                workweek = get_workweek(first_startlot.split()[0])
                
                updated_row = [date, time, workweek, first_startlot, machine_id] + row[1:4] + [offset_x, offset_y, offset_t]
                updated_data_rows.append(updated_row)
            except ValueError as e:
                print(f"Error processing row: {row}. Error: {e}")
    
    updated_data_rows.sort(key=lambda x: (x[6], x[7]), reverse=True)
    
    # Correct UnitLocation ranking for each distinct StripMapID by timestamp
    stripmapid_groups = {}
    for row in updated_data_rows:
        strip_id = row[7]
        if strip_id not in stripmapid_groups:
            stripmapid_groups[strip_id] = []
        stripmapid_groups[strip_id].append(row)
    
    for group in stripmapid_groups.values():
        group.sort(key=lambda x: (x[0], x[1]))  # Sort by Date and Time
        for i, row in enumerate(group):
            row.append(f"Unit {10 - i}")
    
    final_data_rows = []
    for group in stripmapid_groups.values():
        final_data_rows.extend(group)
    
    for i, row in enumerate(final_data_rows):
        stripmapid_count = stripmapid_count_dict[row[7]]
        row.append(stripmapid_count)
        row.append("full" if stripmapid_count == 10 else "partial")
    
    return header, final_data_rows

def write_csv_by_workweek(header, data_rows):
    workweek_files = {}
    
    for row in data_rows:
        workweek = row[2]
        if workweek not in workweek_files:
            file_name = os.path.join(output_folder, f"Module4_WW{workweek}.csv")
            workweek_files[workweek] = open(file_name, 'w', newline='')
            csv_writer = csv.writer(workweek_files[workweek])
            csv_writer.writerow(header)
        
        csv_writer = csv.writer(workweek_files[workweek])
        csv_writer.writerow(row)
    
    for file in workweek_files.values():
        file.close()

def main():
    log_lines = read_log_file(log_file_name)
    header, updated_data_rows = process_data(log_lines)
    write_csv_by_workweek(header, updated_data_rows)
    print("The log file has been successfully converted and separated by workweeks.")

if __name__ == "__main__":
    main()
