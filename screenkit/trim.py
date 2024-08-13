import os
from typing import Optional
import tempfile
import cv2


def trim_video(video_path: str, start_time: float = 0, end_time: Optional[float] = None) -> str:
   # Open the video file
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Error opening video file: {video_path}")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Create a VideoWriter object for the output video
    temp_file = os.path.join(tempfile.gettempdir(), "temp.mp4")
    out = cv2.VideoWriter(str(temp_file), fourcc, fps, (width, height))

    # Calculate the start and end frames
    start_frame = int(start_time * fps)
    if end_time is None:
        end_frame = total_frames
    else:
        end_frame = int(end_time * fps)

    # Read and write the video frames to the output file
    frame_number = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if start_frame <= frame_number <= end_frame:
            out.write(frame)
        frame_number += 1
        if frame_number > end_frame:
            break

    cap.release()
    out.release()
    return temp_file