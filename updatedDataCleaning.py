import os
import re
import shutil  # NEW: to remove existing output folder
import pandas as pd
from typing import Dict, List
import sys
from openpyxl.utils import get_column_letter
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd
from XYAnimator import test


def parse_line(line: str) -> Dict:
    # 1) Determine object type
    if "BsdRadarObjInfo" in line:
        obj_type = "radar"
    elif "BsdImageObjInfo" in line:
        obj_type = "image"
    else:
        return {}

    # 2) Extract x, y, confidence
    x_match = re.search(r"x=(-?\d+)", line)
    y_match = re.search(r"y=(-?\d+)", line)
    conf_match = re.search(r"confidence=(\d+)", line)

    x_val = int(x_match.group(1)) if x_match else None
    y_val = int(y_match.group(1)) if y_match else None
    confidence_val = int(conf_match.group(1)) if conf_match else None

    if obj_type == "radar":
        # 3a) Radar object
        distance = None
        theta = None
        velocity = None
        power = None
        
        raw_search = re.search(r"raw=BsdRadarObjRaw\s*\{([^}]*)\}", line)
        if raw_search:
            raw_content = raw_search.group(1)
            fields = [item.strip() for item in raw_content.split(",")]
            for f in fields:
                k, v = f.split("=")
                k, v = k.strip(), v.strip()
                if k == "distance":
                    distance = int(v)
                elif k == "theta":
                    theta = int(v)
                elif k == "velocity":
                    velocity = int(v)
                elif k == "power":
                    power = int(v)

        return {
            "type": "radar",
            "x": x_val,
            "y": y_val,
            "confidence": confidence_val,
            "distance": distance,
            "theta": theta,
            "velocity": velocity,
            "power": power
        }

    else:
        # 3b) Image object
        left = None
        top = None
        width_ = None
        height_ = None
        
        raw_search = re.search(r"raw=BsdImageObjRaw\s*\{([^}]*)\}", line)
        if raw_search:
            raw_content = raw_search.group(1)
            fields = [item.strip() for item in raw_content.split(",")]
            for f in fields:
                k, v = f.split("=")
                k, v = k.strip(), v.strip()
                if k == "left":
                    left = int(v)
                elif k == "top":
                    top = int(v)
                elif k == "width":
                    width_ = int(v)
                elif k == "height":
                    height_ = int(v)

        return {
            "type": "image",
            "x": x_val,
            "y": y_val,
            "confidence": confidence_val,
            "left": left,
            "top": top,
            "width": width_,
            "height": height_
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

def adjust_excel(writer,sheet_name):
    ws = writer.sheets[sheet_name]  # Get the worksheet object
    # for col in ws.columns:
    #     ws.column_dimensions[col[1].column_letter].auto_size = True
    column_widths = []
    for row in ws.rows:
        for i, cell in enumerate(row):
            if len(column_widths) > i:
                if len(str(cell)) > column_widths[i]:
                    column_widths[i] = len(str(cell))
            else:
                column_widths += [len(str(cell))]
    
    for i, column_width in enumerate(column_widths,1):  # ,1 to start at 1
        ws.column_dimensions[get_column_letter(i)].width = column_width

def sort_and_export(df_radar: pd.DataFrame, df_image: pd.DataFrame, output_excel_path: str):
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        # 1) Radar data
        if not df_radar.empty:
            df_radar['time'] = pd.to_datetime(df_radar['time'])
            df_radar_sorted = df_radar.sort_values(by=['time', 'y'])
            df_radar_sorted.to_excel(writer, sheet_name='radar_data', index=False)
        else:
            print("There is no radar data")
        adjust_excel(writer, "radar_data")
        # 2) Image data
        if not df_image.empty:
            df_image['time'] = pd.to_datetime(df_image['time'])
            df_image_sorted = df_image.sort_values(by=['time', 'y'])
            df_image_sorted.to_excel(writer, sheet_name='image_data', index=False)
        else:
            print("There is no image data")
        adjust_excel(writer,'image_data') 

def filter_radar_entries(df_radar: pd.DataFrame) -> dict:
    if df_radar.empty:
        print("No radar data detected: returning no data")
        return 0
    else:
        # df_radar['velocity'] = df_radar['raw'].apply(lambda d: d.get('velocity', None) if isinstance(d, dict) else None)
        
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
            adjust_excel(writer,sheet_name[:30])

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
        adjust_excel(writer, 'matched_data')
        adjust_excel(writer, 'unmatched_data')

def get_input_folder():
    # The folder containing the .exe at runtime
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    
    # We'll assume there's an "input" folder right next to the .exe
    input_path = os.path.join(exe_dir, 'input')
    return input_path

def get_output_folder():
    """
    Returns a path to 'output' folder located in the same directory as the .exe.
    If the folder already exists, it is removed.
    Then a fresh 'output' folder is created.
    """
    # The directory containing the .exe (or script if not frozen)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        # If not frozen, we can use the directory of this .py file
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    output_folder_path = os.path.join(exe_dir, "output")

    if os.path.exists(output_folder_path):
        shutil.rmtree(output_folder_path)  # remove all old files/folders inside

    os.makedirs(output_folder_path, exist_ok=True)
    return output_folder_path

def animate_xy(df_image, df_radar):
    times = sorted(set(df_image['time'].unique()).union(df_radar['time'].unique()))
    
    fig, (ax_img, ax_rad, ax_both) = plt.subplots(1, 3, figsize=(15, 5))
    lines_x = [0, 3, 6, -3, -6]
    
    def setup_ax(ax):
        ax.set_xlim(-6, 6)
        ax.set_ylim(-1, 175)
        for xv in lines_x:
            ax.axvline(x=xv, color='black', linestyle='--', alpha=0.5)
    
    def update(frame):
        t = times[frame]
        sub_img = df_image[df_image['time'] == t]
        sub_rad = df_radar[df_radar['time'] == t]
        
        for ax in (ax_img, ax_rad, ax_both):
            ax.cla()
            setup_ax(ax)
        
        ax_img.scatter(sub_img['x'], sub_img['y'], c='blue')
        ax_rad.scatter(sub_rad['x'], sub_rad['y'], c='red')
        
        ax_both.scatter(sub_img['x'], sub_img['y'], c='blue')
        ax_both.scatter(sub_rad['x'], sub_rad['y'], c='red')
        
        for _, row in sub_img.iterrows():
            ax_img.text(row['x'], row['y'], f"({row['x']},{row['y']})", color='blue', fontsize=8)
            ax_both.text(row['x'], row['y'], f"({row['x']},{row['y']})", color='blue', fontsize=8)
        for _, row in sub_rad.iterrows():
            ax_rad.text(row['x'], row['y'], f"({row['x']},{row['y']})", color='red', fontsize=8)
            ax_both.text(row['x'], row['y'], f"({row['x']},{row['y']})", color='red', fontsize=8)

        ax_img.set_title(f"Image Only (t={t})")
        ax_rad.set_title(f"Radar Only (t={t})")
        ax_both.set_title(f"Combined (t={t})")

    ani = animation.FuncAnimation(fig, update, frames=len(times), interval=500, repeat=False)
    plt.show()


def main():
    test()
    # NEW: Remove existing "output" folder (if any), then recreate it
    output_folder_path = get_output_folder()
    if os.path.exists(output_folder_path):
        shutil.rmtree(output_folder_path)  # remove all old files/folders inside
    os.makedirs(output_folder_path, exist_ok=True)
    
    # 1) Read logs
    input_folder_path = get_input_folder()
    print()
    df_radar, df_image = read_logs_from_folder(input_folder_path)
    
    # 2) Sort & export => put into "output/" folder
    all_data_path = os.path.join(output_folder_path, "all_data_sorted.xlsx")
    sort_and_export(df_radar, df_image, all_data_path)
    
    # 3) Filter radar & export => put into "output/" folder
    filtered_dict = filter_radar_entries(df_radar)
    filtered_radar_path = os.path.join(output_folder_path, "filtered_radar.xlsx")
    export_filtered_radar(filtered_dict, filtered_radar_path)
    
    # 4) Compare radar vs image => put into "output/" folder
    if not df_radar.empty and not df_image.empty:
        df_matched_timeframes, df_unmatched_timeframes = compare_radar_image(df_radar, df_image)
        comparison_path = os.path.join(output_folder_path, "radar_image_comparison.xlsx")
        export_comparison_to_excel(df_matched_timeframes, df_unmatched_timeframes, comparison_path)
    else:
        print("No comparison made as there is no image or radar data")
    # XYAnimator.XYAnimatorGUI(df_image, df_radar)

    os.system("pause")



if __name__ == "__main__":
    main()