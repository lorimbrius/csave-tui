FSLIST            = "/root/filesystem.usage"  # list of filesystems
DATASET_LIST      = "/usr/local/etc/dumplist" # list of datasets to dump
LASTDUMP_SENTINEL = "/var/preserve/lastdump"  # sentinel file whose mtime
                                              # represents the last time the
                                              # entire system was dumped

def generate_dataset_list():
    with open(DATASET_LIST, 'w', encoding="utf-8") as f_dataset_list, \
         open(FSLIST, 'r', encoding="utf-8")       as f_fslist:
        for fs_line in f_fslist:    # format is SIZE\tMOUNT_POINT
            fs = fs_line.split()[1] # want the filesytem mount point
            f_dataset_list.write(f"{fs}\n")

def make_directories_list():
    directories = []
    
    with open(DATASET_LIST, 'r', encoding="utf-8") as f_dataset_list:
        directories = f_dataset_list.readlines()
        
    return directories