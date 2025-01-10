import matplotlib.pyplot as plt
import pandas as pd
from openpyxl.utils import get_column_letter
import numpy as np

class XYAnimator:
    """
    A class to display 3 subplots:
      1) Image-only data
      2) Radar-only data
      3) Combined data

    It uses integer time steps (t=0,1,2,...) mapped from the original timestamps.
    Allows interactive key-presses to:
      - Pause/Resume animation
      - Move forward/backward in time
      - Jump to a specific t or t-range
      - Toggle coordinate text
      - Toggle "past coords" (keep older frames visible)
    """

    def __init__(self, df_image: pd.DataFrame, df_radar: pd.DataFrame):
        """
        Prepares data (mapping real timestamps to integer steps) and sets up figure/axes.
        """
        # 1) Convert times to a consistent datetime
        df_image['time'] = pd.to_datetime(df_image['time'])
        df_radar['time'] = pd.to_datetime(df_radar['time'])

        # 2) Collect all unique times, sort them, and map to t=0..N-1
        all_times = sorted(set(df_image['time'].unique()) | set(df_radar['time'].unique()))
        self.time_to_index = {t: i for i, t in enumerate(all_times)}
        
        # Create new 't_index' columns in the data
        df_image['t_index'] = df_image['time'].map(self.time_to_index)
        df_radar['t_index'] = df_radar['time'].map(self.time_to_index)

        self.df_image = df_image
        self.df_radar = df_radar

        # Determine total frames
        self.max_t = len(all_times)  # number of integer steps

        # 3) Create figure/subplots
        self.fig, (self.ax_img, self.ax_rad, self.ax_both) = plt.subplots(1, 3, figsize=(15, 5))
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)

        # Prepare the lines we want to draw at x=0, ±3, ±6
        self.x_lines = [0, 3, 6, -3, -6]

        # 4) State variables
        self.current_t = 0              # which integer step we are displaying
        self.paused = False             # is animation paused?
        self.show_coords = True         # toggle coordinate text
        self.show_past = Truepppppppp          # toggle if we keep older frames
        self.past_points_img = []       # store past coords for image
        self.past_points_rad = []       # store past coords for radar

        # For convenience, let's define the axis range:
        self.xmin, self.xmax = -10, 10
        self.ymin, self.ymax = -10, 10

        # 5) Animation Timer
        self.interval_ms = 500  # how many ms between updates when not paused
        self.timer = self.fig.canvas.new_timer(interval=self.interval_ms)
        self.timer.add_callback(self.update_frame)
        self.timer.start()

    def draw_verticals(self, ax):
        """Draw vertical lines at x=0, ±3, ±6."""
        for xv in self.x_lines:
            ax.axvline(x=xv, color='black', linestyle='--', alpha=0.5)
        ax.set_xlim(self.xmin, self.xmax)
        ax.set_ylim(self.ymin, self.ymax)

    def clear_axes(self):
        """Clear all subplots before drawing new data."""
        for ax in (self.ax_img, self.ax_rad, self.ax_both):
            ax.cla()
            self.draw_verticals(ax)

    def update_frame(self):
        """Called periodically (unless paused) or manually to draw the next frame."""
        if not self.paused:
            self.current_t += 1
            if self.current_t >= self.max_t:
                self.current_t = self.max_t - 1  # stay at last
                self.paused = True
        self.draw_current()

    def draw_current(self):
        """Draw data for self.current_t on all subplots."""
        self.clear_axes()

        # Subset data
        sub_img = self.df_image[self.df_image['t_index'] == self.current_t]
        sub_rad = self.df_radar[self.df_radar['t_index'] == self.current_t]

        # If "past coords" are on, accumulate them
        if self.show_past:
            self.past_points_img.append(sub_img)
            self.past_points_rad.append(sub_rad)
        else:
            self.past_points_img = [sub_img]
            self.past_points_rad = [sub_rad]

        # Combine accumulated data
        all_img = pd.concat(self.past_points_img) if self.past_points_img else sub_img
        all_rad = pd.concat(self.past_points_rad) if self.past_points_rad else sub_rad

        # Plot image on left subplot
        self.ax_img.scatter(all_img['x'], all_img['y'], color='blue')
        # Plot radar on middle subplot
        self.ax_rad.scatter(all_rad['x'], all_rad['y'], color='red')
        # Combined on right subplot
        self.ax_both.scatter(all_img['x'], all_img['y'], color='blue')
        self.ax_both.scatter(all_rad['x'], all_rad['y'], color='red')

        # Optionally label coordinates
        if self.show_coords:
            for _, row in all_img.iterrows():
                self.ax_img.text(row['x'], row['y'], f"({row['x']},{row['y']})",
                                 color='blue', fontsize=8)
                self.ax_both.text(row['x'], row['y'], f"({row['x']},{row['y']})",
                                  color='blue', fontsize=8)
            for _, row in all_rad.iterrows():
                self.ax_rad.text(row['x'], row['y'], f"({row['x']},{row['y']})",
                                 color='red', fontsize=8)
                self.ax_both.text(row['x'], row['y'], f"({row['x']},{row['y']})",
                                  color='red', fontsize=8)

        # Titles
        self.ax_img.set_title(f"Image Only (t={self.current_t})")
        self.ax_rad.set_title(f"Radar Only (t={self.current_t})")
        self.ax_both.set_title(f"Combined (t={self.current_t})")

        # Redraw
        self.fig.canvas.draw_idle()

    def on_key_press(self, event):
        """
        Handle key presses:
         - Left/Right arrows: step backward/forward one frame
         - Space: pause/resume
         - c: toggle coords
         - p: toggle "past coords"
         - g: query user to go to a specific t or t range
        """
        if event.key == 'right':
            # step forward
            self.current_t = min(self.current_t + 1, self.max_t - 1)
            self.paused = True
            self.draw_current()
        elif event.key == 'left':
            # step backward
            self.current_t = max(self.current_t - 1, 0)
            self.paused = True
            self.draw_current()
        elif event.key == ' ':
            # toggle pause
            self.paused = not self.paused
            if not self.paused:
                # resume => next frame on next timer
                pass
        elif event.key == 'c':
            # toggle coords
            self.show_coords = not self.show_coords
            self.draw_current()
        elif event.key == 'p':
            # toggle past coords
            self.show_past = not self.show_past
            if not self.show_past:
                # clear accumulations except current
                self.past_points_img = []
                self.past_points_rad = []
            self.draw_current()
        elif event.key == 'g':
            # jump to a specific t or range
            # This is a simple text-based prompt in console.
            val = input("Enter a time index or range (e.g. '10' or '5-10'): ")
            if '-' in val:
                start_s, end_s = val.split('-')
                try:
                    start_i = int(start_s.strip())
                    end_i = int(end_s.strip())
                    start_i = max(0, min(start_i, self.max_t - 1))
                    end_i = max(0, min(end_i, self.max_t - 1))
                    # We'll jump to start_i, then auto-run forward to end_i
                    self.paused = True
                    for i in range(start_i, end_i + 1):
                        self.current_t = i
                        self.draw_current()
                        plt.pause(0.5)  # display each step
                except:
                    print("Invalid range input.")
            else:
                try:
                    idx = int(val.strip())
                    idx = max(0, min(idx, self.max_t - 1))
                    self.current_t = idx
                    self.paused = True
                    self.draw_current()
                except:
                    print("Invalid integer input.")

def main():
    # 1) Example DataFrames
    # In real usage, you'd read from logs or already have df_image/df_radar
    # Here we create some minimal data for demonstration:
    data_img = {
        'time': ['2025-01-02 15:53:39', '2025-01-02 15:53:39', '2025-01-02 15:53:34',
                 '2025-01-02 15:53:40', '2025-01-02 15:53:41'],
        'x': [0, 1, 2, 3, 4],
        'y': [5, 4, 3, 2, 1]
    }
    data_rad = {
        'time': ['2025-01-02 15:53:39', '2025-01-02 15:53:33', '2025-01-02 15:53:31',
                 '2025-01-02 15:53:35','2025-01-02 15:53:40'],
        'x': [0, -1, -2, -3, -4],
        'y': [5, 5, 5, 5, 5]
    }
    df_image = pd.DataFrame(data_img)
    df_radar = pd.DataFrame(data_rad)

    # 2) Create animator
    animator = XYAnimator(df_image, df_radar)

    # 3) Start event loop
    plt.show()

if __name__ == "__main__":
    main()
