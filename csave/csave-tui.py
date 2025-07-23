#!/usr/bin/env python
#
###############################################################################
# CSave, a tape backup script
# TUI implementation
###############################################################################
#

import os
import subprocess
import datetime
from subprocess import Popen
from fs_utils import generate_dataset_list, get_lastdump_mtime, make_directories_list, update_lastdump_sentinel

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

    code, tag = d.radiolist(message,
                            width=width,
                            choices=choices,
                            title=title,
                            backtitle=BACK_TITLE)

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

    items = [(dir, dir, True if dir in selected_dirs else False) for dir in make_directories_list()]
    
    # no_collapse prevents collapsing whitespace in the message
    code, tags = d.buildlist(message,
                             items=items,
                             title=title,
                             backtitle=BACK_TITLE,
                             no_collapse=True)

    return tags if code == Dialog.OK else selected_dirs

def confirm_lastdump_mtime():
    sentinel_mtime    = get_lastdump_mtime()
    sentinel_datetime = datetime.datetime.fromtimestamp(sentinel_mtime)
    sentinel_timestr  = sentinel_datetime.strftime("%Y-%m-%d")
    title             = "Last Backup Time"
    message           = "Enter last backup time in YYYY-mm-dd format:"

    _, string = d.inputbox(message, init=sentinel_timestr, title=title, backtitle=BACK_TITLE)

    return string

def start_backup(backup_mode, block_size, auto_eject, tape_mode, selected_dirs):
    ### DEBUG
    print(f"backup_mode: {backup_mode}\nblock_size: {block_size}\nauto_eject: {auto_eject}\ntape_mode: {tape_mode}\nselected_dirs: {selected_dirs}")

    # Block until the tape is loaded
    load_tape()

    if tape_mode == 'a':
        with Popen(["mt", "eod"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as mt_proc:
            tape_proc_follow(mt_proc)

    lastdump_mtime = ""

    if backup_mode.lower() == "differential":
        lastdump_mtime = confirm_lastdump_mtime()
    
    already_backed_up = []

    def render_already_backed_up():
        return "Already backed up: \n" + '\n'.join(already_backed_up)
    
    try:
        for dir in selected_dirs:
            message = f"Backing up {dir}"
            with Popen([
                    "tar",
                    "c",
                    f"-b{block_size}",
                    "--totals",
                    "--one-file-system",
                    "--exclude .zfs/",
                    f"--newer-mtime {lastdump_mtime}" if len(lastdump_mtime) > 1 else "",
                    "."
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=dir) as tar_proc:

                # This will not block - a programbox would
                d.progressbox(fd=tar_proc.stdout.fileno,
                              text=render_already_backed_up() + f"\n\n{message}",
                              title=f"Backing up {dir}",
                              backtitle=BACK_TITLE)

        update_lastdump_sentinel()

    finally:
        if auto_eject:
            with Popen(["mt", "offl"],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE) as mt_proc:
                tape_proc_follow(mt_proc)
                
        title   = "Backup Complete"
        message = "The following directories were backed up:\n" + render_already_backed_up()
        
        d.scrollbox(message, title=title, backtitle=BACK_TITLE)

def load_tape():
    title   = "Load Tape"
    message = "Please insert a tape."

    d.msgbox(message, title=title, backtitle=BACK_TITLE)

    with Popen(["mt", "status"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as mt_proc:
        tape_proc_follow(mt_proc)

def tape_mode_menu(tape_mode):
    title   = "Tape Mode"
    message = "Select tape mode:"
    width   = 70
    choices = [
        # (tag,       item,                                        status)
        ('Append',    'Append this backup to the end of the tape', tape_mode == 'a'),
        ('Overwrite', 'Overwrite the tape with this backup',       tape_mode == 'o')
    ]

    code, tag = d.radiolist(message,
                            choices=choices,
                            width=width,
                            title=title,
                            backtitle=BACK_TITLE)

    if code in [Dialog.CANCEL, Dialog.ESC]:
        return tape_mode
    else:
        return 'a' if tag == 'Append' else 'o'

def final_confirmation(backup_mode, block_size, auto_eject, tape_mode, selected_dirs):
    title    = "Final Confirmation"
    message  = "Please review the following. Press OK to start backup or Cancel to return to backup menu."
    elements = [
        # (label,         yl, xl, item,                                           yi, xi, field_length, input_length)
        ("Backup mode",   1,  1,   backup_mode,                                   1,  15,  0,            0),
        ("Block size",    2,  1,   str(block_size),                               2,  15,  0,            0),
        ("Auto eject",    3,  1,   "Yes" if auto_eject else "No",                 3,  15,  0,            0),
        ("Tape mode",     4,  1,   "Append" if tape_mode == 'a' else "Overwrite", 4,  15,  0,            0),
        ("Selected dirs", 5,  1,   str(selected_dirs),                            5,  15,  0,            0)
    ]

    code, _ = d.form(message, elements, title=title, backtitle=BACK_TITLE)

    return code == Dialog.OK

def tape_proc_follow(mt_proc):
    mt_proc.wait()

    if mt_proc.returncode != 0:
        title = "Tape Error"
        d.msgbox(mt_proc.stderr.read().decode(), title=title, backtitle=BACK_TITLE)
        os._exit(mt_proc.returncode)

if __name__ == "__main__":
    backup_mode       = "Full"                    # full or differential backup
    block_size        = 512                       # tape block size
    auto_eject        = True                      # eject tape when finished
    tape_mode         = 'o'                       # overwrite by default
    selected_dirs     = make_directories_list()   # directories to back up

    generate_dataset_list()

    code = None

    while True:
        (code,
         backup_mode,
         block_size,
         auto_eject,
         tape_mode,
         selected_dirs) = backup_config_menu(backup_mode,
                                             block_size,
                                             auto_eject,
                                             tape_mode,
                                             selected_dirs)

        if code == Dialog.EXTRA:
            confirmed = final_confirmation(backup_mode,
                                           block_size,
                                           auto_eject,
                                           tape_mode,
                                           selected_dirs)

            if confirmed:
                start_backup(backup_mode, block_size, auto_eject, tape_mode, selected_dirs)
        
        if code in [Dialog.CANCEL, Dialog.ESC]:
            os._exit(0)
