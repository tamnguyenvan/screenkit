import json
import os
import time
import tempfile
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np
from pynput import keyboard, mouse
import mss
import mss.tools

from screenkit.enhance import enhance
from screenkit.utils import pprint, Color, get_data_path


class ScreenRecorder:
    def __init__(self, output_dir: Optional[str] = None, region: Optional[Tuple[int, int, int, int]] = None,
                 fps: int = 30, countdown_time: int = 3, output_raw: bool = False, enhance_params: Dict = {}):
        self.output_dir = output_dir or self.get_default_output_dir()
        self.region = region
        self.fps = fps
        self.countdown_time = countdown_time
        self.output_raw = output_raw
        self.enhance_params = enhance_params
        self.stop_recording = False
        self.mouse_events: Dict[str, List[Dict]] = {"click": [], "move": []}
        self.screen_width, self.screen_height = 0, 0

    @staticmethod
    def get_default_output_dir() -> str:
        home = os.path.expanduser("~")
        videos_dir = os.path.join(home, "Videos", "ScreenKit")
        os.makedirs(videos_dir, exist_ok=True)
        return videos_dir

    def on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if self.screen_width and self.screen_height:
            rel_x, rel_y = x / self.screen_width, y / self.screen_height
            self.mouse_events["click"].append({
                "x": rel_x, "y": rel_y, "button": str(button), "pressed": pressed, "time": time.time()
            })

    def get_mouse_position(self) -> Tuple[float, float]:
        if self.screen_width and self.screen_height:
            x, y = mouse.Controller().position
            return x / self.screen_width, y / self.screen_height
        return 0, 0

    def select_roi(self, screenshot: mss.screenshot.ScreenShot) -> Optional[Tuple[int, int, int, int]]:
        scale = 0.7
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
        frame_height, frame_width = frame.shape[:2]
        new_height, new_width = int(frame_height * scale), int(frame_width * scale)
        scaled_frame = cv2.resize(frame, (new_width, new_height))

        window_name = "Select region"
        x, y, w, h = cv2.selectROI(window_name, scaled_frame, showCrosshair=False)
        x, y = int(x / scale), int(y / scale)
        w, h = int(w / scale), int(h / scale)
        cv2.destroyAllWindows()
        return (x, y, w, h) if w > 0 and h > 0 else None

    def countdown(self, message) -> None:
        for i in range(self.countdown_time, 0, -1):
            print(Color.MAGENTA + f"\r[ScreenKit] - {message} in {i} seconds...", end="", flush=True)
            time.sleep(1)

    def record(self) -> str:
        pprint(f"Recording started. Press Ctrl + Esc to finish. Ctrl+C to cancel.", Color.CYAN)

        with mss.mss() as sct:
            # Get the region would being recorded
            if self.region == "custom":
                try:
                    message = "A window for selecting custom region will be shown"
                    self.countdown(message)
                except KeyboardInterrupt:
                    pprint("\nRecording cancelled.")
                    if os.path.isfile(video_path):
                        os.remove(video_path)
                    return

                screenshot = sct.grab(sct.monitors[0])
                self.screen_height, self.screen_width = np.array(screenshot).shape[:2]
                self.enhance_params.update({
                    "screen_width": self.screen_width,
                    "screen_height": self.screen_height
                })

                print()
                self.region = self.select_roi(screenshot)
                if not self.region:
                    return

            frame_interval = 1 / self.fps
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            video_filename = f"ScreenKit-{timestamp}.mp4"
            video_path = os.path.join(tempfile.gettempdir(), video_filename)

            if self.countdown_time > 0:
                try:
                    message = "Starting recording"
                    self.countdown(message)
                except KeyboardInterrupt:
                    pprint("\nRecording cancelled.")
                    if os.path.isfile(video_path):
                        os.remove(video_path)
                    return

            print(Color.CYAN + "\r[ScreenKit] - Recording started!                  ", end="", flush=True)
            monitor = {"top": self.region[1], "left": self.region[0], "width": self.region[2], "height": self.region[3]} if self.region else sct.monitors[0]
            self.enhance_params["record_region"] = monitor

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            video_writer = None

            with keyboard.Listener(on_press=self.on_key_press) as key_listener, \
                 mouse.Listener(on_click=self.on_click) as mouse_listener:

                start_time = time.time()
                try:
                    while not self.stop_recording:
                        loop_start = time.time()

                        screenshot = sct.grab(monitor)
                        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)

                        if video_writer is None:
                            height, width, _ = frame.shape
                            video_writer = cv2.VideoWriter(video_path, fourcc, self.fps, (width, height))

                        video_writer.write(frame)

                        rel_x, rel_y = self.get_mouse_position()
                        current_time = time.time() - start_time
                        self.mouse_events["move"].append({
                            "x": rel_x, "y": rel_y, "time": current_time
                        })

                        print(Color.CYAN + f"\r[ScreenKit] - Elapsed Time: {current_time:.2f} seconds", end="", flush=True)

                        time.sleep(max(0, frame_interval - (time.time() - loop_start)))

                except KeyboardInterrupt:
                    print("\nRecording cancelled.")
                    if os.path.isfile(video_path):
                        os.remove(video_path)
                    return

            if video_writer:
                video_writer.release()

            print()
            pprint(f"Recording stopped. Enhancing video...", Color.GREEN)

            json_path = get_data_path(video_path)
            self.save_json_data(json_path)

            output_path = os.path.join(self.output_dir, video_filename)
            output_path = enhance(
                video_path=video_path,
                output_path=output_path,
                data_path=json_path,
                enhance_params=self.enhance_params
            )

            os.remove(json_path)
            pprint(f"The result video is available at {output_path}", Color.GREEN)
            return output_path

    def on_key_press(self, key: keyboard.Key) -> bool:
        try:
            if key == keyboard.Key.esc and keyboard.Controller().pressed(keyboard.Key.ctrl):
                self.stop_recording = True
                return False
        except AttributeError:
            pass
        return True

    def save_json_data(self, json_path: str) -> None:
        with open(json_path, "w") as f:
            json.dump(self.mouse_events, f)


def record_screen(output_dir: Optional[str] = None, region: Optional[Tuple[int, int, int, int]] = None,
           fps: int = 30, countdown_time: int = 3, output_raw: bool = False, enhance_params: Dict = {}) -> str:
    recorder = ScreenRecorder(output_dir, region, fps, countdown_time, output_raw, enhance_params)
    return recorder.record()