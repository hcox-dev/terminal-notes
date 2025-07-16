import os
import json
import datetime
import curses
import subprocess
from curses import wrapper
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.align import Align

NOTES_DIR = os.path.expanduser("~/.terminal_notes")
CONFIG_FILE = os.path.join(NOTES_DIR, "config.json")
INDEX_FILE = os.path.join(NOTES_DIR, "index.json")
TEMPLATE_FILE = os.path.join(NOTES_DIR, "TEMPLATE.md")

DEFAULT_CONFIG = {
    "editor": os.getenv("EDITOR", "nano"),
    "preview_cmd": "cat",
    "date_format": "%Y-%m-%d %H:%M",  # More readable format: YYYY-MM-DD HH:MM
    "theme": {
        "highlight_fg": "black",
        "highlight_bg": "cyan",
        "normal_fg": "white",
        "normal_bg": "black"
    },
    "max_notes": 100,  # Limit the number of notes to keep the index manageable
    "storage": NOTES_DIR,
}

DEFAULT_TEMPLATE = """---
title: {title}
description: {description}
created_at: {created_at}
updated_at: {updated_at}
---

# {title}

## Notes

Write your notes here.

```python
# Example code block
print('Hello, world!')
```
"""

def ensure_dirs():
    os.makedirs(NOTES_DIR, exist_ok=True)
    if not os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "w") as f:
            json.dump({}, f)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    if not os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "w") as f:
            f.write(DEFAULT_TEMPLATE)

def load_index():
    with open(INDEX_FILE, "r") as f:
        return json.load(f)

def save_index(index):
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def load_template():
    """Load and return the template content, falling back to default if file doesn't exist."""
    try:
        with open(TEMPLATE_FILE, "r") as f:
            return f.read()
    except FileNotFoundError:
        return DEFAULT_TEMPLATE

def format_template(template_content, title, description, timestamp):
    """Format the template with the provided values."""
    current_time = datetime.datetime.now()
    return template_content.format(
        title=title,
        description=description,
        created_at=timestamp,
        updated_at=timestamp
    )

def create_note(title, description="", config=None):
    if config is None:
        config = load_config()
    if not title or title.strip() == "":
        raise ValueError("Title cannot be empty")
    if not description or description.strip() == "":
        raise ValueError("Description cannot be empty")
    
    files = os.listdir(NOTES_DIR)
    if len(files) >= config.get("max_notes", DEFAULT_CONFIG["max_notes"]):
        raise Exception("Maximum number of notes reached. Please delete some notes before creating new ones.")

    timestamp = datetime.datetime.now().strftime(config.get("date_format", "%Y-%m-%d_%H-%M-%S"))
    filename = f"{timestamp}.md"
    filepath = os.path.join(config.get("storage", NOTES_DIR), filename)
    if os.path.exists(filepath):
        raise FileExistsError(f"Note with title '{title}' already exists.")
    
    # Load and format the template
    template_content = load_template()
    note_content = format_template(template_content, title, description, timestamp)
    
    with open(filepath, "w") as f:
        f.write(note_content)
    index = load_index()
    index[filename] = {
        "title": title,
        "created": timestamp
    }
    save_index(index)
    return filename

def edit_note(filename, config):
    editor = config.get("editor", "nano")
    os.system(f"{editor} {os.path.join(NOTES_DIR, filename)}")

def delete_note(filename):
    filepath = os.path.join(NOTES_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    index = load_index()
    if filename in index:
        del index[filename]
    save_index(index)

def preview_note(filename):
    filepath = os.path.join(NOTES_DIR, filename)
    with open(filepath, 'r') as f:
        md = Markdown(f.read())
    console = Console()
    console.print(Panel(md, title=filename, expand=True))
    input("\nPress Enter to return to menu...")

def display_notes(stdscr):
    config = load_config()
    curses.curs_set(0)
    k = 0
    cursor = 0
    index = load_index()
    notes = list(index.items())[::-1]  # Newest first
    theme = config.get("theme", DEFAULT_CONFIG["theme"])

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, getattr(curses, f"COLOR_{theme['highlight_fg'].upper()}", curses.COLOR_BLACK),
                     getattr(curses, f"COLOR_{theme['highlight_bg'].upper()}", curses.COLOR_CYAN))
    curses.init_pair(2, getattr(curses, f"COLOR_{theme['normal_fg'].upper()}", curses.COLOR_WHITE),
                     getattr(curses, f"COLOR_{theme['normal_bg'].upper()}", curses.COLOR_BLACK))

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        header = " Terminal Notes "
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(0, max(0, (width - len(header)) // 2), header)
        stdscr.attroff(curses.A_BOLD)
        stdscr.addstr(1, 0, "─" * width)
        stdscr.addstr(2, 2, "[Enter] Open  [n] New  [d] Delete  [p] Preview  [q] Quit")

        if not notes:
            stdscr.addstr(4, 4, "No notes found. Press 'n' to create a new note.")
        else:
            for i, (fname, meta) in enumerate(notes):
                line = f"{meta['title']} ({meta['created']})"
                if i == cursor:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(i + 4, 4, line[:width - 8])
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.attron(curses.color_pair(2))
                    stdscr.addstr(i + 4, 4, line[:width - 8])
                    stdscr.attroff(curses.color_pair(2))

        k = stdscr.getch()

        if k == curses.KEY_UP and notes:
            cursor = max(0, cursor - 1)
        elif k == curses.KEY_DOWN and notes:
            cursor = min(len(notes) - 1, cursor + 1)
        elif k == ord('q'):
            break
        elif k == ord('n'):
            curses.echo()
            while True:
                stdscr.clear()
                stdscr.addstr(0, 0, "Create New Note")
                stdscr.addstr(1, 0, "─" * 20)
                stdscr.addstr(3, 0, "Enter title: ")
                title = stdscr.getstr().decode()
                
                if not title or title.strip() == "":
                    stdscr.addstr(5, 0, "Error: Title cannot be empty. Press any key to try again...")
                    stdscr.getch()
                    continue
                
                stdscr.addstr(4, 0, "Enter description: ")
                description = stdscr.getstr().decode()
                
                if not description or description.strip() == "":
                    stdscr.addstr(6, 0, "Error: Description cannot be empty. Press any key to try again...")
                    stdscr.getch()
                    continue
                
                break
            
            curses.noecho()
            
            try:
                fname = create_note(title, description, config)
                edit_note(fname, config)
                index = load_index()
                notes = list(index.items())[::-1]
                cursor = 0
            except Exception as e:
                stdscr.addstr(height - 1, 0, f"Error: {str(e)}. Press any key to continue...")
                stdscr.getch()
        elif k == ord('d') and notes:
            delete_note(notes[cursor][0])
            index = load_index()
            notes = list(index.items())[::-1]
            cursor = min(cursor, max(0, len(notes) - 1))
        elif k == ord('\n') or k == 10:
            if notes:
                edit_note(notes[cursor][0], config)
                index = load_index()
                notes = list(index.items())[::-1]
        elif k == ord('p') and notes:
            curses.endwin()
            preview_note(notes[cursor][0])
            stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            stdscr.keypad(True)

        stdscr.refresh()

def run_app(stdscr):
    display_notes(stdscr)

def main():
    ensure_dirs()
    wrapper(run_app)

if __name__ == "__main__":
    main()
