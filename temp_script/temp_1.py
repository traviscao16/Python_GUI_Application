import csv

def filter_jig_ids(input_file_path, output_file_path, search_terms):
    filtered_rows = []

    # Read and filter the input CSV
    with open(input_file_path, mode='r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            if any(term in row['ATTR_VALUE'] for term in search_terms):
                filtered_rows.append(row)

    # Save filtered rows to a new CSV
    with open(output_file_path, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)

# Example usage
input_path = r"C:\Users\zbrzyy\Downloads\tracejigID(in).csv"  # Replace with your actual input file path
output_path = r"C:\Users\zbrzyy\Downloads\tracejigID_filltered.csv" # Desired output file name
search_terms = ['5219', '4058', '5293']

filter_jig_ids(input_path, output_path, search_terms)
