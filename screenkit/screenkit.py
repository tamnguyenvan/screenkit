from pathlib import Path
import click
import os
import json
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
    with open(CACHE_FILE, 'w') as f:
        json.dump({"output_path": output_path}, f)

def load_from_cache():
    """Loads the output path from the cache file."""
    if not CACHE_FILE.exists():
        raise FileNotFoundError("Cache file not found.")
    with open(CACHE_FILE, 'r') as f:
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
@click.option('-o', '--output', help="Output folder for screenshots and video")
@click.option('-r', '--region', callback=parse_region, help="Screen region to capture (x,y,width,height)")
@click.option('-f', '--fps', type=int, default=30, help="Frames per second (default: 30)")
@click.option('-p', '--padding', callback=parse_padding, default=0.1, help="Padding for the beautified result (default: 0.1)")
@click.option('-b', '--background', type=str, default="default-wallpaper-1", help="Background color for the recording (default: black)")
@click.option('-w', '--webcam', type=str, default="0", help="Webcam id to be used")
@click.option('--macos-titlebar', is_flag=True, help="Make the titlebar look like MacOS")
@click.option('--border-radius', type=float, default=10, help="Border radius for the recording (default: 10)")
@click.option('--cursor-scale', type=float, default=1.0, help="Cursor scale (default: 1.0)")
@click.option('--shadow-blur', type=int, default=10, help="Shadow blur radius (default: 10)")
@click.option('--shadow-opacity', type=float, default=0.5, help="Shadow opacity (default: 0.5)")
@click.option('--output-raw', is_flag=True, help="Output file for raw recording data")
@click.option('--countdown', type=int, default=3, help="Countdown time before starting the recording in seconds (default: 3)")
def record(output, region, fps, padding, background, webcam, macos_titlebar, border_radius, cursor_scale, shadow_blur, shadow_opacity, output_raw, countdown):
    """Start screen recording with specified options."""
    settings = {
        "Output folder": output,
        "Region": region if region else "Full screen",
        "FPS": fps,
        "Padding": padding,
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
