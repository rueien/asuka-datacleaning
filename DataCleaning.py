import re
import sys
from pathlib import Path
from datetime import datetime

def filter_radar_data(input_folder, output_file):
    """
    Reads radar data from all .txt files in the input folder, filters based on specified criteria,
    categorizes them into defined intervals, sorts each category by 'y' ascending,
    and writes the filtered data to the output file.
    """
    # Regular expression to extract x, y, and velocity values
    pattern = re.compile(r'x=(-?\d+), y=(-?\d+), .*?velocity=(-?\d+)')

    # Initialize dictionaries for categorized entries
    filtered_entries = {
        'Category 1 (y < 20 and velocity ≠ 0)': [],
        'Category 2 (20 ≤ y ≤ 80 and velocity ≠ 0)': [],
        'Category 3 (y > 80 and velocity ≠ 0)': [],
        'Category 4 (x = 0, y = 0, and velocity = 0)': []
    }

    # Ensure input folder exists
    input_path = Path(input_folder)
    if not input_path.is_dir():
        print(f"Error: Input folder '{input_folder}' does not exist.")
        sys.exit(1)

    # Process each .txt file in the input folder
    txt_files = list(input_path.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in '{input_folder}'.")
        sys.exit(1)

    for file_index, input_file in enumerate(txt_files, 1):
        print(f"Processing file {file_index}/{len(txt_files)}: '{input_file.name}'")
        current_timestamp = ""

        try:
            with open(input_file, 'r', encoding = 'utf-8') as infile:
                for line_num, line in enumerate(infile, 1):
                    line = line.strip()
                    if not line:
                        continue  # Skip empty lines

                    # Check if the line is a timestamp
                    timestamp_match = re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+', line)
                    if timestamp_match:
                        current_timestamp = line
                        continue  # Move to the next line

                    # Assume the line contains one or more BsdRadarObjInfo entries
                    entries = re.findall(r'BsdRadarObjInfo \{([^}]+)\}', line)
                    if not entries:
                        print(f"  Warning: No BsdRadarObjInfo found on line {line_num} in '{input_file.name}'.")
                        continue

                    for entry in entries:
                        match = pattern.search(entry)
                        if match:
                            x = int(match.group(1))
                            y = int(match.group(2))
                            velocity = int(match.group(3))

                            # Apply filtering criteria
                            condition_cat1 = (y < 20 and velocity != 0)
                            condition_cat2 = (20 <= y <= 80 and velocity != 0)
                            condition_cat3 = (y > 80 and velocity != 0)
                            condition_cat4 = (x == 0 and y == 0 and velocity == 0)

                            if condition_cat1:
                                filtered_entries['Category 1 (0 < y < 20 and velocity ≠ 0)'].append(
                                    (y, current_timestamp, f"BsdRadarObjInfo {{{entry}}}")
                                )

                            if condition_cat2:
                                filtered_entries['Category 2 (20 ≤ y ≤ 80 and velocity ≠ 0)'].append(
                                    (y, current_timestamp, f"BsdRadarObjInfo {{{entry}}}")
                                )

                            if condition_cat3:
                                filtered_entries['Category 3 (y > 80 and velocity ≠ 0)'].append(
                                    (y, current_timestamp, f"BsdRadarObjInfo {{{entry}}}")
                                )

                            if condition_cat4:
                                filtered_entries['Category 4 (x = 0, y = 0, and velocity = 0)'].append(
                                    (y, current_timestamp, f"BsdRadarObjInfo {{{entry}}}")
                                )
                        else:
                            print(f"  Warning: Unable to parse entry on line {line_num} in '{input_file.name}': {entry}")

        except Exception as e:
            print(f"  Error processing file '{input_file.name}': {e}")
            continue

    # Function to sort entries by 'y' ascending
    def sort_entries(entries):
        return sorted(entries, key=lambda x: x[0])

    # Sort each category's entries by 'y' ascending
    for category in filtered_entries:
        if category != 'Category 4 (x = 0, y = 0, and velocity = 0)':  # Category 4 has y=0
            filtered_entries[category] = sort_entries(filtered_entries[category])
        else:
            # All y=0, no need to sort
            pass

    # Write the categorized and sorted entries to the output file
    try:
        with open(output_file, 'w', encoding = 'utf-8') as outfile:
            for category, entries in filtered_entries.items():
                outfile.write(f"=== {category} ===\n\n")
                for entry in entries:
                    y, timestamp, obj_info = entry
                    outfile.write(f"{timestamp}\n{obj_info}\n\n")
                outfile.write("\n")  # Add extra newline between categories

        # Print summary
        print(f"\nFiltering and sorting complete. Results written to '{output_file}'.")
        for category, entries in filtered_entries.items():
            print(f"  {category}: {len(entries)} entries.")
    except Exception as e:
        print(f"Error writing to output file '{output_file}': {e}")
        sys.exit(1)

def main():
    """
    Main function to execute the radar data filtering.
    Assumes the script is placed inside the 'radar_filter' directory with 'input' and 'output' folders.
    """
    # Define input and output folders
    input_folder = Path(__file__).parent / "input"
    output_folder = Path(__file__).parent / "output"
    output_folder.mkdir(exist_ok=True)  # Create output folder if it doesn't exist
    output_file = output_folder / "filtered_output.txt"

    # Call the filtering function
    filter_radar_data(input_folder, output_file)

if __name__ == "__main__":
    main()
