import os
import re
import shutil  # NEW: to remove existing output folder
import pandas as pd
from typing import Dict, List

def parse_line(line: str) -> Dict:
    if "BsdRadarObjInfo" in line:
        obj_type = "radar"
    elif "BsdImageObjInfo" in line:
        obj_type = "image"
    else:
        return {}
    
    x_match = re.search(r"x=(-?\d+)", line)
    y_match = re.search(r"y=(-?\d+)", line)
    conf_match = re.search(r"confidence=(\d+)", line)
    # prob change this line to include the raw data as their own columns
    raw_data = {}
    if obj_type == "radar":
        raw_search = re.search(r"raw=BsdRadarObjRaw\s*\{([^}]*)\}", line)
        if raw_search:
            raw_content = raw_search.group(1)
            for item in raw_content.split(","):
                k, v = item.strip().split("=")
                raw_data[k.strip()] = int(v.strip())
    else:
        raw_search = re.search(r"raw=BsdImageObjRaw\s*\{([^}]*)\}", line)
        if raw_search:
            raw_content = raw_search.group(1)
            for item in raw_content.split(","):
                k, v = item.strip().split("=")
                raw_data[k.strip()] = int(v.strip())
    
    return {
        "type": obj_type,
        "x": int(x_match.group(1)) if x_match else None,
        "y": int(y_match.group(1)) if y_match else None,
        "confidence": int(conf_match.group(1)) if conf_match else None,
        # this line is a bit sussy, i think i can just transform raw data into their own fields 
        "raw": raw_data
    }

def read_logs_from_folder(folder_path: str):
    radar_records = []
    image_records = []
    
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            filepath = os.path.join(folder_path, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
                
            current_time = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+", line):
                    current_time = line
                else:
                    record = parse_line(line)
                    if record and current_time:
                        record["time"] = current_time
                        if record["type"] == "radar":
                            radar_records.append(record)
                        elif record["type"] == "image":
                            image_records.append(record)
    
    df_radar = pd.DataFrame(radar_records)
    df_image = pd.DataFrame(image_records)
    return df_radar, df_image

def sort_and_export(df_radar: pd.DataFrame, df_image: pd.DataFrame, output_excel_path: str):
    if not df_radar.empty: 
        df_radar['time'] = pd.to_datetime(df_radar['time'])
        df_radar_sorted = df_radar.sort_values(by=['time','y'])
        with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
            df_radar_sorted.to_excel(writer, sheet_name='radar_data', index=False)
    else:
        print("There is no radar data")
    if not df_image.empty:
        df_image['time'] = pd.to_datetime(df_image['time'])
        df_image_sorted = df_image.sort_values(by=['time','y'])
        with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
            df_image_sorted.to_excel(writer, sheet_name='image_data', index=False)
    else:
        print("There is no image data")
    

 

def filter_radar_entries(df_radar: pd.DataFrame) -> dict:
    if df_radar.empty:
        print("No radar data detected: returning no data")
        return 0
    else:
        df_radar['velocity'] = df_radar['raw'].apply(lambda d: d.get('velocity', None) if isinstance(d, dict) else None)
        
        cat1 = df_radar[(df_radar['y'] < 20) & (df_radar['velocity'] != 0)]
        cat2 = df_radar[(df_radar['y'] >= 20) & (df_radar['y'] <= 80) & (df_radar['velocity'] != 0)]
        cat3 = df_radar[(df_radar['y'] > 80) & (df_radar['velocity'] != 0)]
        cat4 = df_radar[(df_radar['x'] == 0) & (df_radar['y'] == 0) & (df_radar['velocity'] == 0)]
        
        filtered_entries = {
            'Category 1 (y < 20 and velocity ≠ 0)': cat1,
            'Category 2 (20 ≤ y ≤ 80 and velocity ≠ 0)': cat2,
            'Category 3 (y > 80 and velocity ≠ 0)': cat3,
            'Category 4 (x = 0, y = 0, and velocity = 0)': cat4
        }
        
        return filtered_entries

def export_filtered_radar(filtered_dict: dict, output_excel_path: str):
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        for cat_name, df_cat in filtered_dict.items():
            sheet_name = cat_name.replace("(", "").replace(")", "").replace(" ", "_").replace("≤", "LE").replace("≥", "GE").replace(">", "GT").replace("<", "LT").replace("=", "EQ")
            print(f"{cat_name}: {len(df_cat)} entries")
            df_cat.to_excel(writer, sheet_name=sheet_name[:30], index=False)

def compare_radar_image(df_radar: pd.DataFrame, df_image: pd.DataFrame):
    """
    Simplified approach based on your steps:

    (1) Group radar by time.
    (2) For each radar time-frame, get the image subset at the same time.
    (3) Check if EVERY radar row has a 1-to-1 match in the image group (by x,y,confidence).
    (4) If any radar row is unmatched, mark the ENTIRE time-frame as unmatched (including all radar & image data).
    (5) Otherwise, the ENTIRE time-frame is matched.
    (6) Compute the overall % of matched radar data vs. total radar data.

    Returns:
      df_matched_timeframes: Each row is a full time-frame (Radar + Image) that matched.
      df_unmatched_timeframes: Each row is a full time-frame (Radar + Image) that failed matching.
      overall_match_percentage: A float representing percentage of matched radar data across all time frames.
    """
    # Ensure datetime
    df_radar['time'] = pd.to_datetime(df_radar['time'])
    df_image['time'] = pd.to_datetime(df_image['time'])
    
    # Sort times
    unique_times = sorted(df_radar['time'].unique())  # only times that appear in radar

    total_radar_count = 0
    matched_radar_count = 0

    matched_timeframes = []
    unmatched_timeframes = []

    for t in unique_times:
        radar_subset = df_radar[df_radar['time'] == t].copy()
        image_subset = df_image[df_image['time'] == t].copy()
        
        radar_rows = radar_subset.to_dict(orient='records')
        image_rows = image_subset.to_dict(orient='records')

        # We only care that EVERY radar row has a match in the image set
        # "It doesn't matter if the image group has more data."
        all_radar_matched = True

        for rrow in radar_rows:
            # Attempt to find a matching row in the image set:
            # We compare x,y,confidence exactly. If found => OK, else => unmatched.
            match_found = any(
                (rrow['x'] == irow['x'] and
                 rrow['y'] == irow['y'] and
                 rrow['confidence'] == irow['confidence'])
                for irow in image_rows
            )
            if not match_found:
                all_radar_matched = False
                break

        # Keep track of how many radar objects we had
        total_radar_count += len(radar_rows)

        if all_radar_matched and len(radar_rows) > 0:
            # This time frame is fully matched
            matched_radar_count += len(radar_rows)
            matched_timeframes.append({
                "time": t,
                "radar_data": radar_rows,
                "image_data": image_rows
            })
        else:
            # If ANY radar row is unmatched, the ENTIRE time-frame goes to unmatched
            unmatched_timeframes.append({
                "time": t,
                "radar_data": radar_rows,
                "image_data": image_rows
            })

    # Compute overall match percentage
    if total_radar_count > 0:
        overall_match_percentage = (matched_radar_count / total_radar_count) * 100
    else:
        overall_match_percentage = 0.0
    print(f"Overall match percentage: {overall_match_percentage}")
    # Convert the matched/unmatched timeframes into DataFrames if desired
    df_matched_timeframes = pd.DataFrame(matched_timeframes)
    df_unmatched_timeframes = pd.DataFrame(unmatched_timeframes)

    return df_matched_timeframes, df_unmatched_timeframes

def export_comparison_to_excel(df_summary: pd.DataFrame, df_matched: pd.DataFrame, output_excel_path: str):
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name='matched_data', index=False)
        df_matched.to_excel(writer, sheet_name='unmatched_data', index=False)

def main():
    # NEW: Remove existing "output" folder (if any), then recreate it
    output_dir = "output"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)  # remove all old files/folders inside
    os.makedirs(output_dir, exist_ok=True)
    
    # 1) Read logs
    df_radar, df_image = read_logs_from_folder("input")
    
    # 2) Sort & export => put into "output/" folder
    all_data_path = os.path.join(output_dir, "all_data_sorted.xlsx")
    sort_and_export(df_radar, df_image, all_data_path)
    
    # 3) Filter radar & export => put into "output/" folder
    filtered_dict = filter_radar_entries(df_radar)
    filtered_radar_path = os.path.join(output_dir, "filtered_radar.xlsx")
    export_filtered_radar(filtered_dict, filtered_radar_path)
    
    # 4) Compare radar vs image => put into "output/" folder
    if not df_radar.empty and not df_image.empty:
        df_matched_timeframes, df_unmatched_timeframes = compare_radar_image(df_radar, df_image)
        comparison_path = os.path.join(output_dir, "radar_image_comparison.xlsx")
        export_comparison_to_excel(df_matched_timeframes, df_unmatched_timeframes, comparison_path)
    else:
        print("No comparison made as there is no image or radar data")

if __name__ == "__main__":
    main()