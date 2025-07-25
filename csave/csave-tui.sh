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
lastdump_mtime=$(stat -f %Sm $LASTDUMP_SENTINEL)

# Functions
backup_config_menu () {
    local title="Backup Configuration"
    local message="Please review the following:"
    local ok_label="Edit Selected Option"
    local cancel_label="Exit"
    local extra_label="Start Backup"
    local backup_mode_label="$(echo $backup_mode | awk '{print toupper(substr($0,1,1)) substr($0,2)}')" # capitalize first letter

    case $auto_eject in
        'Y')
            auto_eject_label=Yes
            ;;
        'N')
            auto_eject_label=No
            ;;
    esac

    case $tape_mode in
        'a')
            tape_mode_label="Append"
            ;;
        'o')
            tape_mode_label="Overwrite"
            ;;
    esac

    local tag=$(dialog --title "$title" --backtitle "$BACK_TITLE" \
        --stdout --menu "$message" 0 0 0                          \
        "Backup mode"            "$backup_mode_label"             \
        "Block size"             "$block_size"                    \
        "Eject when finished"    "$auto_eject_label"              \
        "Tape mode"              "$tape_mode_label"               \
        "Directories to back up" ""                               )

    case $? in
        ($DIALOG_CANCEL|$DIALOG_ESC)
            exit 0
            ;;
        $DIALOG_OK)
            dispatch_choice "$tag"
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

    local tag=$(dialog --stdout --title "$title" --backtitle "$BACK_TITLE"                                              \
        --radiolist "$message" 0 $width 0                                                                               \
        "Full"          "Back up all files, regardless of last change date"             $backup_mode_full               \
        "Differential"  "Only back up files that have changed since the last backup",   $backup_mode_differential       )

    if [ $? -eq $DIALOG_OK ]; then
        backup_mode="$(echo $tag | tr '[:upper:]' '[:lower:]')"
    fi

    unset backup_mode_full
    unset backup_mode_differential

    backup_config_menu
}

enter_block_size () {
    local title="Block Size"
    local message="Enter tape block size (default 512):"

    local string=$(dialog --title "$title" --backtitle "$BACK_TITLE" \
        --stdout --inputbox "$message" 0 0 $block_size)

    if [ $? -eq $DIALOG_OK ]; then
        block_size=$string
    fi

    backup_config_menu
}

select_auto_eject () {
    local title="Auto Eject"
    local message="Should the tape automatically eject when the backup is finished?"

    dialog --title "$title" --backtitle "$BACK_TITLE" --yesno "$message" 0 0

    case $? in
        $DIALOG_OK)
            auto_eject='Y'
            ;;
        $DIALOG_CANCEL)
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

        items="$items $dir $dir $status"
    done

    local tags=$(dialog --title "$title" --backtitle "$BACK_TITLE" --no-collapse \
        --stdout --buildlist "$message" 0 0 0 $items)

    if [ $? -eq $DIALOG_OK ]; then
        selected_dirs="$tags"
    fi

    backup_config_menu
}

confirm_lastdump_mtime () {
    local title="Last Backup Time"
    local message="Enter last backup time in YYYY-mm-dd format:"

    lastdump_mtime=$(dialog --no-cancel --title "$title" --stdout \
         --backtitle "$BACK_TITLE" --inputbox "$message" 0 0 "$lastdump_mtime")
}

assemble_backup_message () {
    local already_backed_up_header="Already backed up:\n"
    local curdir="$1"

    if [ ${#already_backed_up} -gt 1 ]; then
        message="$already_backed_up_header"

        for dir in "$already_backed_up"; do
            message="${message}${dir}\n"
        done
    fi

    message="${message}\n${Now backing up} ${curdir}\n"

    echo -e "$message"
}

assemble_completed_message () {
    for dir in "$already_backed_up"; do
        completed_message="${completed_message}\n${dir}"
    done

    echo -e "$completed_message"
}

start_backup () {
    # Block until tape is loaded
    load_tape

    if [ $tape_mode = 'a' ]; then # append mode
        # fast forward to end of data
        mt_err=$(mt eod 2>&1 > /dev/null)
        rc=$?

        if [ $rc -ne 0 ]; then
            dialog --title "Tape Error" --backtitle "$BACK_TITLE" \
                --infobox "$mt_err" 0 0

            exit $rc
        fi
    fi

    if [ "$backup_mode" = "differential" ]; then
        confirm_lastdump_mtime
        newer_mtime_arg="--newer-mtime $lastdump_mtime"
    fi

    final_confirmation

    # actually start backing up
    for dir in "$selected_dirs"; do
    ( # Subshell to prevent the script's wd from becoming the directory we're 
      # backing up.
        cd "$dir"
        message=$(assemble_backup_message "$dir")

        # Shell substitution to capture tar's error stream in a variable, send
        # its output to dialog, and preserve its exit code.
        {
            tar_err=$(tar c -b$block_size --totals --one-file-system 
                --exclude .zfs/ $newer_mtime_arg . 2>&1 >&3 3>&-)

            export tarrc=$?
        } 3>&1 | dialog --title "$message" --backtitle "$BACK_TITLE" \
            --stdout --progressbox "$message" 0 0

        # tar error handler
        if [ $tarrc -ne 0 ]; then
            dialog --title "Tape Error" --backtitle "$BACK_TITLE" \
                --infobox "$tar_err" 0 0

            exit $tarrc
        fi

        unset tarrc

        already_backed_up="$already_backed_up $dir"
    )
    done

    # backup is done
    if [ $backup_mode = "full" ]; then
        touch "$LASTDUMP_SENTINEL"
    fi

    completed_message=$(assemble_completed_message)

    local completed_title="Backup Complete"
    local completed_message="The following directories were backed up:\n${completed_message}"

    dialog --title "$completed_title" --backtitle "$BACK_TITLE" \
        --msgbox "$completed_message" 0 0

    backup_config_menu
}

load_tape () {
    local title="Load Tape"
    local message="Please insert a tape"

    dialog --title "$title" --backtitle "$BACK_TITLE" --msgbox "$message" 0 0

    local mt_err=$(mt status 2>&1 > /dev/null)
    local rc=$?

    if [ $rc -ne 0 ]; then
        dialog --title "Tape Error" --backtitle "$BACK_TITLE" --infobox "$mt_err" 0 0
        exit $rc
    fi
}

select_tape_mode () {
    local title="Tape Mode"
    local message="Select tape mode:"
    local width=70

    case $tape_mode in
        'a')
            append_status=ON
            overwrite_status=OFF
            ;;
        'o')
            append_status=OFF
            overwrite_status=ON
            ;;
    esac

    local tag=$(dialog --title "$title" --backtitle "$BACK_TITLE"                  \
        --stdout --radiolist "$message" 0 $width 0                                 \
        "Append"    "Append this backup to the end of the tape" $append_status     \
        "Overwrite" "Overwrite the tape with this backup"       $overwrite_status  )

    if [ $? -eq $DIALOG_OK ]; then
        tape_mode="$(echo $tag | tr '[:upper:]' '[:lower:]' | cut -c 1-1)"
    fi

    backup_config_menu
}

final_confirmation () {
    local title="Final Confirmation"
    local message="Please review the following. Press OK to start backup or Cancel to return to backup menu."
    local backup_mode_label="$(echo $backup_mode | awk '{print toupper(substr($0,1,1)) substr($0,2)}')" # capitalize first letter
    
    case $auto_eject in
        'Y')
            auto_eject_label=Yes
            ;;
        'N')
            auto_eject_label=No
            ;;
    esac

    case $tape_mode in
        'a')
            tape_mode_label="Append"
            ;;
        'o')
            tape_mode_label="Overwrite"
            ;;
    esac

    if [ ${#lastdump_mtime} -gt 1 ]; then
        lastdump_mtime_line="'Last backup date' 6 1 $lastdump_mtime 6 15 0 0"
    fi

    dialog --title "$title" --backtitle "$BACK_TITLE" --form "$message" 0 0 0 \
        "Backup mode"   1   1   $backup_mode_label  1   15  0   0             \
        "Block size"    2   1   $block_size         2   15  0   0             \
        "Auto eject"    3   1   $auto_eject_label   3   15  0   0             \
        "Tape mode"     4   1   $tape_mode_label    4   15  0   0             \
        "Selected dirs" 5   1   $selected_dirs      5   15  0   0             \
        "$lastdump_mtime_line"

    if [ $? -ne $DIALOG_OK ]; then
        backup_config_menu
    fi
}

backup_config_menu