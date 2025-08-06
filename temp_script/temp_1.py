import csv

def load_search_terms(search_terms_file):
    """Load search terms from a CSV file (assumes one term per row)."""
    terms = []
    with open(search_terms_file, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Avoid empty rows
                terms.append(row[0].strip())
    return terms

def filter_jig_ids(input_file_path, output_file_path, search_terms):
    filtered_rows = []
    matched_terms = set()

    # Read and filter the input CSV
    with open(input_file_path, mode='r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            for term in search_terms:
                if term in row['ATTR_VALUE']:
                    filtered_rows.append(row)
                    matched_terms.add(term)
                    break  # Avoid duplicate matches for the same row

    # Save filtered rows to a new CSV
    with open(output_file_path, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)

    # Report unmatched terms
    unmatched_terms = set(search_terms) - matched_terms
    if unmatched_terms:
        print("Search terms not found in the input file:")
        for term in unmatched_terms:
            print(f" - {term}")
    else:
        print("All search terms were matched.")

# Example usage
input_path = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\TraceJig_W20-W31.csv"
output_path = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\TraceJig_result_2.csv"
search_terms_file = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\search_terms.csv"

search_terms = load_search_terms(search_terms_file)
filter_jig_ids(input_path, output_path, search_terms)
