import os
import tempfile
from dataclasses import dataclass
from colorama import init, Fore, Style

init(autoreset=True)

@dataclass
class Color:
    WHITE = Fore.WHITE
    RED = Fore.RED
    GREEN = Fore.GREEN
    BLUE = Fore.BLUE
    YELLOW = Fore.YELLOW
    CYAN = Fore.CYAN
    MAGENTA = Fore.MAGENTA
    RESET = Style.RESET_ALL

def pprint(message: str, color: str = Color.MAGENTA, prefix: str = "[ScreenKit]", end: str = "\n", bold: bool = False) -> None:
    """Prints a message with the specified color and formatting."""
    bold_start = Style.BRIGHT if bold else ""
    print(color + bold_start + f"{prefix} - {message}", end=end + Color.RESET)

def pprint_table(header: str, data: dict, color: str = Color.GREEN, width: int = 30) -> None:
    """Prints a table with a header and data, with fixed column width."""
    # Print the header
    print(Color.CYAN + f"{header}")
    print(Color.CYAN + "-" * (width * 2 + 4))

    # Define the format for each row
    row_format = f"{{:<{width}}} {{:>{width}}}"

    # Print each row
    for key, value in data.items():
        print(row_format.format(key, str(value)))

    print(Color.CYAN + "-" * (width * 2 + 4))


def get_data_path(video_path: str) -> str:
    filename = os.path.basename(video_path)
    filename_wo_extension = os.path.splitext(filename)[0]
    temp_dir = tempfile.gettempdir()
    return os.path.join(temp_dir, f"{filename_wo_extension}.json")