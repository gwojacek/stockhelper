# Functions for coloring text in the terminal using ANSI codes
def color_text(text, color):
    """Function to color text in the terminal"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "reset": "\033[0m",
    }
    return f"{colors[color]}{text}{colors['reset']}"
