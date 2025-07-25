#!/bin/sh
#
###############################################################################
# CSave, a tape backup script
# TUI implementation
###############################################################################
#

# Globals
BACK_TITLE="CSave" # program title
DIALOG_CANCEL=1    # Dialog's Cancel button
DIALOG_ERROR=-1    # Dialog's error code
DIALOG_ESC=255     # Dialog's escape code
DIALOG_EXTRA=3     # Dialog's extra button
DIALOG_HELP=2      # Dialog's Help button
DIALOG_TIMEOUT=5   # Dialog's timeout code
DIALOG_OK=0        # Dialog's OK button
DATASET_LIST=$(cat < /usr/local/etc/dumplist)
LASTDUMP_SENTINEL="/var/preserve/lastdump"

backup_mode="full" # Full vs. differential backup
block_size=512     # Tape block size
auto_eject='Y'     # Should the tape automatically eject when backup finishes
tape_mode='o'      # (a)ppend or (o)verwrite
selected_dirs=""   # List of directories to back up
lastdump_mtime=`stat -f %Sm $LASTDUMP_SENTINEL`

# Functions
backup_config_menu () {
    local title="Backup Configuration"
    local message="Please review the following:"
    local ok_label="Edit Selected Option"
    local cancel_label="Exit"
    local extra_label="Start Backup"

    local tag=`dialog --title "$title" --backtitle "$BACK_TITLE" --menu "$message" 0 0 0 \
        "Backup mode"            "$backup_mode"                                          \
        "Block size"             "$block_size"                                           \
        "Eject when finished"    "$auto_eject"                                           \
        "Tape mode"              "$tape_mode"                                            \
        "Directories to back up" ""                                                      `

    case $? in
        $DIALOG_CANCEL|$DIALOG_ESC)
            exit 0
            ;;
        $DIALOG_OK)
            dispatch_choice $tag
            ;;
        $DIALOG_EXTRA)
            start_backup
            ;;
        *)
            exit $code
            ;;
    esac
}

dispatch_choice () {
    case $1 in
        "Backup mode")
            select_backup_mode
            ;;
        "Block size")
            enter_block_size
            ;;
        "Eject when finished")
            select_auto_eject
            ;;
        "Tape mode")
            select_tape_mode
            ;;
        "Directories to back up")
            select_directories
            ;;
    esac
}

select_backup_mode () {
    local title="Backup Mode"
    local message="Select backup mode:"
    local width=90
    
    case $backup_mode in
        full)
            backup_mode_full=ON
            backup_mode_differential=OFF
            ;;
        differential)
            backup_mode_full=OFF
            backup_mode_differential=ON
            ;;
    esac

    local tag=`dialog --title "$title" --backtitle "$BACK_TITLE" --radiolist "$message" 0 $width 0                     \
        "Full"          "Back up all files, regardless of last change date"             $backup_mode_full               \
        "Differential"  "Only back up files that have changed since the last backup",   $backup_mode_differential       `

    if [ $? -eq DIALOG_OK ]; then
        backup_mode=${tag,,} # magic to convert $tag to lower case
    fi

    unset backup_mode_full
    unset backup_mode_differential

    backup_config_menu
}

enter_block_size () {
    local title="Block Size"
    local message="Enter tape block size (default 512):"

    local string=`dialog --title "$title" --backtitle "$BACK_TITLE" --inputbox "$message" 0 0 $block_size`

    if [ $? -eq DIALOG_OK ]; then
        block_size=$string
    fi

    backup_config_menu
}

select_auto_eject () {
    local title="Auto Eject"
    local message="Should the tape automatically eject when the backup is finished?"

    dialog --title "$title" --backtitle "$BACK_TITLE" --yesno "$message" 0 0

    case $? in
        DIALOG_OK)
            auto_eject='Y'
            ;;
        DIALOG_CANCEL)
            auto_eject='N'
            ;;
    esac

    backup_config_menu
}

select_directories () {
    local title="Select Directories"
    local message=$(cat <<EOF
Select directories to back up:

Keys: SPACE     to select or deselect the highlighted item
      ^         to move the focus to the left list (unselected items)
      $         to move the focus to the right list (selected items)
      TAB       to toggle focus between the left and right lists
      ENTER     to press the focused button (OK or Cancel)
EOF
    )

    local items=""

    for dir in "$DATASET_LIST"; do
        grep "$dir" "$selected_dirs"

        if [ $? -eq 0 ]; then
            status=ON
        else
            status=OFF
        fi

        items="$items dir dir $status"
    done

    local tags=`dialog --title "$title" --backtitle "$BACK_TITLE" --no-collapse \
        --buildlist "$message" 0 0 0 $items`

    if [ $? -eq DIALOG_OK ]; then
        selected_dirs="$tags"
    fi

    backup_config_menu
}

confirm_lastdump_mtime () {
    local title="Last Backup Time"
    local message="Enter last backup time in YYYY-mm-dd format:"

    lastdump_mtime=`dialog --no-cancel --title "$title" --backtitle "$BACK_TITLE" --inputbox "$message" 0 0 "$lastdump_mtime"`
}

start_backup () {
    # Block until tape is loaded
    load_tape

    if [ $tape_mode = 'a' ]; then # append mode
        # fast forward to end of data
        mterr=$(mt eod 2>&1 > /dev/null)
        rc=$?

        if [ $rc -ne 0 ]; then
            dialog --title "Tape Error" --backtitle "$BACK_TITLE" --infobox "$mterr" 0 0
            exit $rc
        fi
    fi

    if [ "$backup_mode" = "differential" ]; then
        confirm_lastdump_mtime
    fi

    final_confirmation

    # actually start backing up
    already_backed_up=""
}