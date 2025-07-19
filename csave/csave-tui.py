import os

# Globals
BLOCK_SIZE        = 512                       # tape block size
FSLIST            = "/root/filesystem.usage"  # list of filesystems
DATASET_LIST      = "/usr/local/etc/dumplist" # list of datasets to dump
LASTDUMP_SENTINEL = "/var/preserve/lastdump"  # sentinel file whose mtime
                                              # represents the last time the
                                              # entire system was dumped
AUTO_EJECT        = 'Y'                       # eject tape when finished
BACK_TITLE        = "CSave"                   # program title

# Initialize dialog
from dialog import Dialog

d = Dialog()

def generate_dataset_list():
    with open(DATASET_LIST, 'w', encoding="utf-8") as f_dataset_list, \
         open(FSLIST, 'r', encoding="utf-8")       as f_fslist:
        for fs_line in f_fslist:    # format is SIZE\tMOUNT_POINT
            fs = fs_line.split()[1] # want the filesytem mount point
            f_dataset_list.write(f"{fs}\n")
            
def backup_config_menu(backup_mode):
    title   = "Backup Configuration"
    message = "Please review the following:"
    entries = [
        # (tag, value)
        ("Backup mode", backup_mode),
        ("Block size", str(BLOCK_SIZE)),
        ("Eject when finished", AUTO_EJECT),
        ("Directories to back up...", '')
    ]
    
    choice = d.menu(message, choices=entries, title=title, backtitle=BACK_TITLE)
        
def make_directories_list():
    directories = []
    
    with open(DATASET_LIST, 'r', encoding="utf-8") as f_dataset_list:
        directories = f_dataset_list.readlines()
        
    return directories

if __name__ == "__main__":
    backup_config_menu("full")
