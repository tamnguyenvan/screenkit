import os
import json
from pathlib import Path

import click
from PIL import Image

from screenkit.record import record_screen
from screenkit.utils import pprint, pprint_table, Color
from screenkit.trim import trim_video
from screenkit import config

CACHE_FILE = Path("video_cache.json")


def parse_region(ctx, param, value):
    if value is None or value == "custom":
        return value

    try:
        x, y, w, h = map(int, value.split(','))
        return x, y, w, h
    except:
        raise click.BadParameter("Region must be x,y,width,height")

def parse_padding(ctx, param, value):
    try:
        num = float(value)
        if num < 0:
            raise click.BadParameter("Padding must be a non-negative number.")
        return num
    except ValueError:
        raise click.BadParameter("Padding must be a number.")

def save_to_cache(output_path):
    """Saves the output path to the cache file."""
    if not os.path.isdir(config.DEFAULT_CACHE_DIR):
        os.makedirs(config.DEFAULT_CACHE_DIR, exist_ok=True)

    cache_path = os.path.join(config.DEFAULT_CACHE_DIR, CACHE_FILE)
    with open(cache_path, 'w') as f:
        json.dump({"output_path": output_path}, f)

def load_from_cache():
    """Loads the output path from the cache file."""
    cache_path = os.path.join(config.DEFAULT_CACHE_DIR, CACHE_FILE)
    if not cache_path.exists():
        raise FileNotFoundError("Cache file not found.")
    with open(cache_path, 'r') as f:
        return json.load(f).get("output_path")

@click.group()
def cli():
    """ScreenKit CLI - A tool for screen recording with various features."""
    print(Color.YELLOW + """\

 ____                           _  ___ _
/ ___|  ___ _ __ ___  ___ _ __ | |/ (_) |_
\___ \ / __| '__/ _ \/ _ \ '_ \| ' /| | __|
 ___) | (__| | |  __/  __/ | | | . \| | |_
|____/ \___|_|  \___|\___|_| |_|_|\_\_|\__|

          """)
    pprint("Welcome to ScreenKit CLI!", color=Color.CYAN, bold=True)

@cli.command()
@click.option('-o', '--output', help="Output folder for screenshots and video", default=config.DEFAULT_OUTPUT_DIR)
@click.option('-r', '--region', callback=parse_region, help="Screen region to capture (x,y,width,height) or custom. Full screen if not set")
@click.option('-f', '--fps', type=int, default=config.DEFAULT_FPS, help=f"Frames per second (default: {config.DEFAULT_FPS})")
@click.option('-p', '--padding', callback=parse_padding, default=config.DEFAULT_PADDING, help=f"Padding for the beautified result (default: {config.DEFAULT_PADDING})")
@click.option('-b', '--background', type=str, default=config.DEFAULT_BACKGROUND, help=f"Background color for the recording (default: {config.DEFAULT_BACKGROUND})")
@click.option('-w', '--webcam', type=str, default=config.DEFAULT_WEBCAM, help=f"Webcam id to be used (default: {config.DEFAULT_WEBCAM})")
@click.option('--macos-titlebar', is_flag=True, help="Make the titlebar look like MacOS")
@click.option('--border-radius', type=float, default=config.DEFAULT_BORDER_RADIUS, help=f"Border radius for the recording (default: {config.DEFAULT_BORDER_RADIUS})")
@click.option('--cursor-scale', type=float, default=config.DEFAULT_CURSOR_SCALE, help=f"Cursor scale (default: {config.CURSOR_SCALE})")
@click.option('--shadow-blur', type=int, default=config.DEFAULT_SHADOW_BLUR, help=f"Shadow blur radius (default: {config.DEFAULT_SHADOW_BLUR})")
@click.option('--shadow-opacity', type=float, default=config.DEFAULT_SHADOW_OPACITY, help=f"Shadow opacity (default: {config.DEFAULT_SHADOW_OPACITY})")
@click.option('--output-raw', is_flag=True, help="Output file for raw recording data")
@click.option('--countdown', type=int, default=config.DEFAULT_COUNTDOWN, help=f"Countdown time before starting the recording in seconds (default: {config.DEFAULT_COUNTDOWN})")
def record(output, region, fps, padding, background, webcam, macos_titlebar, border_radius, cursor_scale, shadow_blur, shadow_opacity, output_raw, countdown):
    """Start screen recording with specified options."""
    settings = {
        "Output folder": output,
        "Region": region if region else "Full screen",
        "FPS": fps,
        "Padding": f"{padding * 100}%" if 0 <= padding <= 1.0 else padding,
        "Background color": background,
        "Shadow blur": shadow_blur,
        "Shadow opacity": shadow_opacity,
        "Border radius": border_radius,
        "Raw output file": output_raw
    }

    pprint_table("Recording Settings", settings, color=Color.GREEN)

    enhance_params = {
        "padding": padding,
        "background": background,
        "webcam": webcam,
        "macos_titlebar": macos_titlebar,
        "border_radius": border_radius,
        "cursor_scale": cursor_scale,
        "shadow_blur": shadow_blur,
        "shadow_opacity": shadow_opacity
    }

    pprint("Starting screen recording. Please wait...", color=Color.CYAN, bold=True)
    output_path = record_screen(output, region, fps, countdown, output_raw=output_raw, enhance_params=enhance_params)

    # Save the output path to cache after recording
    save_to_cache(output_path)


@cli.command()
@click.option('-s', '--start-time', type=float, default=0, help="Start time for trimming in seconds.")
@click.option('-e', '--end-time', type=float, default=None, help="End time for trimming in seconds.")
def trim(start_time, end_time):
    """Trim the recorded video based on start and end times."""
    try:
        video_path = load_from_cache()
        if not video_path:
            raise FileNotFoundError("No video found in cache. Please record a video first.")

        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        pprint(f"Trimming video from {start_time}s to {end_time}s...", color=Color.CYAN, bold=True)

        # Replace the original video with the trimmed video
        temp_file = trim_video(video_path, start_time, end_time)
        os.replace(temp_file, video_path)

        pprint(f"Trimmed video saved to {video_path}.", color=Color.GREEN)

    except FileNotFoundError as e:
        pprint(str(e), color=Color.RED)
    except Exception as e:
        pprint(f"An error occurred: {str(e)}", color=Color.RED)


@cli.group()
def background():
    """Manage background wallpapers"""
    pass

@background.command()
def list():
    """List available wallpapers in the images/wallpapers directory."""
    wallpaper_dir = Path(__file__).parent / config.BACKGROUND_DIR
    wallpapers = [os.path.splitext(f)[0] for f in os.listdir(wallpaper_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    if not wallpapers:
        pprint("No wallpapers found in the images/wallpapers directory.", color=Color.RED)
        return

    pprint("Available wallpapers:", color=Color.CYAN, bold=True)
    for wallpaper in wallpapers:
        pprint(f"- {wallpaper}", color=Color.CYAN)

@background.command()
@click.argument('wallpaper', type=str)
def show(wallpaper):
    """Show a specific wallpaper."""
    try:
        wallpaper_path = Path(__file__).parent / config.BACKGROUND_MAP.get(wallpaper, "")
        img = Image.open(wallpaper_path)
        img.show()
        pprint(f"Displaying wallpaper: {wallpaper}", color=Color.CYAN)
    except IOError:
        pprint(f"Cannot open image file: {wallpaper}", color=Color.RED)
    except Exception as e:
        pprint(f"An error occurred: {str(e)}", color=Color.RED)

if __name__ == "__main__":
    cli()
