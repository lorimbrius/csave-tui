import os
from fs_utils import generate_dataset_list, make_directories_list
import subprocess
from subprocess import Popen

# Globals
BACK_TITLE = "CSave" # program title

# Initialize dialog
from dialog import Dialog

d = Dialog()

def backup_config_menu(backup_mode, block_size, auto_eject, tape_mode, selected_dirs):
    title   = "Backup Configuration"
    message = "Please review the following:"
    choices = [
        # (tag,                 value)
        ("Backup mode",         backup_mode),
        ("Block size",          str(block_size)),
        ("Eject when finished", "Yes" if auto_eject else "No"),
        ("Tape mode",           "Append" if tape_mode == 'a' else "Overwrite"),
        ("Directories to back up...", '')
    ]

    ok_label     = "Edit Selected Option"
    cancel_label = "Exit"
    extra_label  = "Start Backup"
    
    code, tag = d.menu(message,
                       choices=choices,
                       title=title,
                       backtitle=BACK_TITLE,
                       ok_label=ok_label,
                       cancel_label=cancel_label,
                       extra_button=True,
                       extra_label=extra_label)

    if code in [Dialog.CANCEL, Dialog.ESC, Dialog.EXTRA]:
        return (code, backup_mode, block_size, auto_eject, tape_mode, selected_dirs)

    match tag.lower():
        case "backup mode":
            backup_mode = select_backup_mode(backup_mode)
        case "block size":
            block_size = enter_block_size(block_size)
        case "eject when finished":
            auto_eject = select_auto_eject(auto_eject)
        case "tape mode":
            tape_mode = tape_mode_menu(tape_mode)
        case "directories to back up...":
            selected_dirs = select_directories_to_back_up(selected_dirs)

    return (code, backup_mode, block_size, auto_eject, tape_mode, selected_dirs)

def select_backup_mode(backup_mode):
    title   = "Backup Mode"
    message = "Select backup mode:"
    width   = 90 
    choices = [
        # (tag,          item,                                                         status)
        ("Full",         "Back up all files, regardless of last change date",          backup_mode.lower() == "full"),
        ("Differential", "Only back up files that have changed since the last backup", backup_mode.lower() == "differential")
    ]

    code, tag = d.radiolist(message, width=width, choices=choices, title=title, backtitle=BACK_TITLE)

    return tag if code == Dialog.OK else backup_mode

def enter_block_size(block_size):
    title   = "Block Size"
    message = "Enter tape block size (default 512):"
    
    code, string = d.inputbox(message, init=str(block_size), title=title, backtitle=BACK_TITLE)

    return string if code == Dialog.OK else block_size

def select_auto_eject(auto_eject):
    title   = "Auto Eject"
    message = "Should the tape automatically eject when the backup is finished?"

    code = d.yesno(message, title=title, backtitle=BACK_TITLE)

    return True if code == Dialog.OK else False if code == Dialog.CANCEL else auto_eject

def select_directories_to_back_up(selected_dirs):
    title   = "Select Directories"
    message = """ Select directories to back up:

    Keys: SPACE     to select or deselect the highlighted item
          ^         to move the focus to the left list (unselected items)
          $         to move the focus to the right list (selected items)
          TAB       to toggle focus between left and right lists
          ENTER     to press the focused button (OK or Cancel)
    """ 

    items   = [(dir, dir, True if dir in selected_dirs else False) for dir in make_directories_list()]
    
    print(items)

    code, tags = d.buildlist(message, items=items, title=title, backtitle=BACK_TITLE)

    return tags if code == Dialog.OK else selected_dirs

def start_backup(backup_mode, block_size, auto_eject, tape_mode, selected_dirs):
    ### DEBUG
    print(f"backup_mode: {backup_mode}\nblock_size: {block_size}\nauto_eject: {auto_eject}\ntape_mode: {tape_mode}\nselected_dirs: {selected_dirs}")

    # Block until the tape is loaded
    load_tape()

def load_tape():
    title   = "Load Tape"
    message = "Please insert a tape."

    d.msgbox(message, title=title, backtitle=BACK_TITLE)

    with Popen(["mt", "status"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as mt_proc:
        mt_proc.wait()

        if mt_proc.returncode != 0:
            title = "Tape Error"
            d.msgbox(mt_proc.stderr.read().decode(), title=title, backtitle=BACK_TITLE)
            os._exit(mt_proc.returncode)

def tape_mode_menu(tape_mode):
    title   = "Tape Mode"
    message = "Select tape mode:"
    width   = 70
    choices = [
        # (tag,       item,                                        status)
        ('Append',    'Append this backup to the end of the tape', tape_mode == 'a'),
        ('Overwrite', 'Overwrite the tape with this backup',       tape_mode == 'o')
    ]

    code, tag = d.radiolist(message, choices=choices, width=width, title=title, backtitle=BACK_TITLE)

    if code in [Dialog.CANCEL, Dialog.ESC]:
        return tape_mode
    else:
        return 'a' if tag == 'Append' else 'o'

if __name__ == "__main__":
    backup_mode       = "Full"                    # full or differential backup
    block_size        = 512                       # tape block size
    auto_eject        = True                      # eject tape when finished
    tape_mode         = 'o'                       # overwrite by default
    selected_dirs     = make_directories_list()   # directories to back up

    generate_dataset_list()

    code = None

    while code not in [Dialog.CANCEL, Dialog.ESC, Dialog.EXTRA]:
        code, backup_mode, block_size, auto_eject, tape_mode, selected_dirs = backup_config_menu(backup_mode, block_size, auto_eject, tape_mode, selected_dirs)

    if code == Dialog.EXTRA:
        start_backup(backup_mode, block_size, auto_eject, tape_mode, selected_dirs)

    os._exit(0)
