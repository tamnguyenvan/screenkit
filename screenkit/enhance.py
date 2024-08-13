import re
import os
import json
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import cv2
import numpy as np
from tqdm import tqdm
from PIL import Image, ImageDraw, ImageFilter

from screenkit import config

class CacheManager:
    def __init__(self):
        self.mask: Dict[Tuple, np.ndarray] = {}
        self.shadow: Dict[Tuple, Image.Image] = {}

    def get_cache_key(self, x_offset: int, y_offset: int, radius: int, shadow_blur: int, shadow_opacity: float) -> Tuple:
        return (x_offset, y_offset, radius, shadow_blur, shadow_opacity)

cache = CacheManager()

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert HEX color to RGB tuple"""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def is_hex_color(hex_color: str) -> bool:
    return (hex_color.startswith("#") and len(hex_color) == 7) or len(hex_color) == 6

def get_wallpaper_path(background: str) -> Optional[Path]:
    if os.path.isfile(background):
        return Path(background)

    path = Path(__file__).parent / config.BACKGROUND_MAP.get(background, "")
    return path if path.is_file() else None

def create_background(size: Tuple[int, int], color: Tuple[int, int, int]) -> np.ndarray:
    """Create a background image of the given color and size"""
    if isinstance(color, str):
        if re.match(r"^#[0-9A-Fa-f]{6}$", color):
            color = hex_to_rgb(color)
        else:
            raise ValueError("Invalid color string. Use HEX code.")
    elif isinstance(color, tuple):
        if len(color) != 3 or not all(0 <= c <= 255 for c in color):
            raise ValueError("Invalid RGB tuple. Each value should be between 0 and 255.")
    else:
        raise ValueError("Color must be a HEX string or RGB tuple.")

    return np.full((size[1], size[0], 3), color, dtype=np.uint8)

def draw_filled_rounded_rectangle(img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int], radius: int, color: int, resolution: int = 16) -> np.ndarray:
    """Draw a filled rounded rectangle using Bézier curves"""
    x1, y1 = pt1
    x2, y2 = pt2

    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)

    pts = np.array([
        (x1, y1 + radius), (x1 + radius, y1),
        (x2 - radius, y1), (x2, y1 + radius),
        (x2, y2 - radius), (x2 - radius, y2),
        (x1 + radius, y2), (x1, y2 - radius),
    ], dtype=np.int32)
    cv2.fillPoly(img, [pts], color, cv2.LINE_AA)

    corner_pts = [
        [(x1, y1 + radius), (x1, y1), (x1 + radius, y1)],
        [(x2 - radius, y1), (x2, y1), (x2, y1 + radius)],
        [(x2, y2 - radius), (x2, y2), (x2 - radius, y2)],
        [(x1 + radius, y2), (x1, y2), (x1, y2 - radius)]
    ]

    for corner in corner_pts:
        pts = np.array([
            [(1-t)**2 * corner[0][0] + 2*(1-t)*t * corner[1][0] + t**2 * corner[2][0],
             (1-t)**2 * corner[0][1] + 2*(1-t)*t * corner[1][1] + t**2 * corner[2][1]]
            for t in np.linspace(0, 1, resolution)
        ], dtype=np.int32)
        cv2.fillPoly(img, [pts], color, cv2.LINE_AA)

    return img

def apply_border_radius_with_shadow(background: Image.Image, foreground: Image.Image, x_offset: int, y_offset: int, radius: int, shadow_blur: int, shadow_opacity: float) -> np.ndarray:
    if isinstance(background, np.ndarray):
        background = Image.fromarray(cv2.cvtColor(background, cv2.COLOR_BGR2RGB))
    if isinstance(foreground, np.ndarray):
        foreground = Image.fromarray(cv2.cvtColor(foreground, cv2.COLOR_BGR2RGB))

    cache_key = cache.get_cache_key(x_offset, y_offset, radius, shadow_blur, shadow_opacity)

    if radius > 0:
        if cache_key not in cache.mask:
            mask = np.zeros(shape=(foreground.size[1], foreground.size[0]), dtype=np.uint8)
            mask = draw_filled_rounded_rectangle(mask, (0, 0), foreground.size, radius, 255)
            cache.mask[cache_key] = Image.fromarray(mask)
        foreground.putalpha(cache.mask[cache_key])
    else:
        foreground.putalpha(Image.new("L", foreground.size, 255))

    if shadow_blur > 0:
        if cache_key not in cache.shadow:
            shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle([(x_offset, y_offset),
                                           (x_offset + foreground.width, y_offset + foreground.height)],
                                           radius, fill=(0, 0, 0, int(255 * shadow_opacity)))
            shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
            cache.shadow[cache_key] = shadow
        shadow = cache.shadow[cache_key]
    else:
        shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))

    result = Image.alpha_composite(background.convert("RGBA"), shadow)
    result.paste(foreground, (x_offset, y_offset), foreground)

    return cv2.cvtColor(np.array(result), cv2.COLOR_RGBA2BGR)

def render_cursor(frame: np.ndarray, cursor_image: np.ndarray, x_offset: int, y_offset: int, scale: float = 1.0) -> np.ndarray:
    if cursor_image.ndim < 3 or cursor_image.shape[2] != 4:
        raise ValueError("Cursor image must be BGRA")

    frame_height, frame_width = frame.shape[:2]
    if x_offset < 0 or x_offset > frame_width or y_offset < 0 or y_offset > frame_height:
        return frame

    if scale > 0:
        new_size = (int(cursor_image.shape[1] * scale * config.CURSOR_SCALE),
                    int(cursor_image.shape[0] * scale * config.CURSOR_SCALE))
        cursor_image = cv2.resize(cursor_image, new_size)

    cursor_height, cursor_width = cursor_image.shape[:2]
    x_end = min(x_offset + cursor_width, frame_width)
    y_end = min(y_offset + cursor_height, frame_height)

    cropped_cursor = cursor_image[:y_end-y_offset, :x_end-x_offset, :]
    mask = cropped_cursor[:, :, 3]
    cursor_rgb = cropped_cursor[:, :, :3]

    roi = frame[y_offset:y_end, x_offset:x_end, :]
    frame[y_offset:y_end, x_offset:x_end, :] = cv2.add(
        cv2.bitwise_and(cursor_rgb, cursor_rgb, mask=mask),
        cv2.bitwise_and(roi, roi, mask=cv2.bitwise_not(mask))
    )
    return frame

def render_traffic_light_buttons(frame: np.ndarray, color: Tuple[int, int, int] = (255, 255, 255), height: int = 42) -> np.ndarray:
    _, width = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (width, height), color, -1)

    left_margin, button_radius, button_spacing = 13, 7, 8
    button_y = height // 2

    for i, color in enumerate([(84, 92, 254), (46, 188, 253), (62, 201, 36)]):
        center = (left_margin + button_spacing * (i + 1) + button_radius * (2 * i + 1), button_y)
        cv2.ellipse(frame, center, (button_radius, button_radius), 0, 0, 360, color, -1, cv2.LINE_AA)

    return frame

def enhance(video_path: str, output_path: str, data_path: Optional[str] = None, enhance_params: Dict[str, Any] = {}) -> str:
    screen_width = enhance_params.get("screen_width")
    screen_height = enhance_params.get("screen_height")
    record_region = enhance_params.get("record_region", {})
    padding = enhance_params.get("padding", 0)
    background = enhance_params.get("background", "default-wallpaper-1")
    macos_titlebar = enhance_params.get("macos_titlebar")
    border_radius = enhance_params.get("border_radius", 0)
    cursor_scale = enhance_params.get("cursor_scale", 1.0)
    shadow_blur = enhance_params.get("shadow_blur", 0)
    shadow_opacity = enhance_params.get("shadow_opacity", 0)

    mouse_events = {}
    if data_path and os.path.isfile(data_path):
        with open(data_path, "r") as f:
            mouse_events = json.load(f)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Error opening video file")

    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    space_x, space_y = max(0, screen_width - orig_width), max(0, screen_height - orig_height)
    if space_x <= space_y:
        padding_x = int(padding * screen_width) if isinstance(padding, float) and 0 <= padding <= 1 else int(padding)
        padding_y = int(padding_x * orig_height / orig_width)
    else:
        padding_y = int(padding * screen_height) if isinstance(padding, float) and 0 <= padding <= 1 else int(padding)
        padding_x = int(padding_y * orig_width / orig_height)
    new_width = min(screen_width - 2 * padding_x, orig_width)
    new_height = min(screen_height - 2 * padding_y, orig_height)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (screen_width, screen_height))

    if isinstance(background, str):
        if path := get_wallpaper_path(background):
            background_frame = cv2.imread(str(path))
            background_frame = cv2.resize(background_frame, (screen_width, screen_height))
        elif is_hex_color(background):
            background_frame = create_background((screen_width, screen_height), hex_to_rgb(background))
        else:
            background_frame = create_background((screen_width, screen_height), (255, 255, 255))
    elif isinstance(background, tuple) and len(background) == 3:
        background_frame = create_background((screen_width, screen_height), background)
    else:
        raise ValueError("Invalid background input. Provide an image path, HEX code, or RGB tuple.")

    cursor_image = cv2.imread(str(Path(__file__).parent / config.CURSOR_IMAGE_PATH), cv2.IMREAD_UNCHANGED)

    frame_count = 0
    start_time = mouse_events.get("move", [{}])[0].get("time", 0)

    with tqdm(total=total_frames, desc="Enhancing Video", unit="frame") as pbar:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            resized_frame = cv2.resize(frame, (new_width, new_height))
            if enhance_params.get("output_raw"):
                background_with_frame = resized_frame
            else:
                if macos_titlebar:
                    resized_frame = render_traffic_light_buttons(resized_frame)

                current_time = start_time + (frame_count / fps)

                latest_mouse_event = next((event for event in reversed(mouse_events.get("move", []))
                                           if event["time"] <= current_time), None)

                if latest_mouse_event:
                    cursor_x = int(latest_mouse_event["x"] * screen_width) - record_region["left"]
                    cursor_y = int(latest_mouse_event["y"] * screen_height) - record_region["top"]
                    resized_frame = render_cursor(resized_frame, cursor_image, cursor_x, cursor_y, cursor_scale)

                background_with_frame = apply_border_radius_with_shadow(
                    background=background_frame.copy(),
                    foreground=resized_frame,
                    x_offset=(screen_width - new_width) // 2,
                    y_offset=(screen_height - new_height) // 2,
                    radius=border_radius,
                    shadow_blur=shadow_blur,
                    shadow_opacity=shadow_opacity
                )

            out.write(background_with_frame)
            frame_count += 1
            pbar.update(1)

    cap.release()
    out.release()
    cv2.destroyAllWindows()

    return output_path