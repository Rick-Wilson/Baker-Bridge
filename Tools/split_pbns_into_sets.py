import os
import re

def create_board_subsets(num_boards=4):
    """
    Process each subfolder (in alphabetical order) in the current folder:
    - Look for an 'All' folder.
    - Find the first .pbn file in the 'All' folder.
    - Use the base name of this .pbn file for constructing the subset filenames.
    - Split the file into a preamble (everything before the first "[Board")
      and individual board sections (each starting with "[Board").
    - Create new files containing groups of num_boards boards.
      Each new file will have the preamble, followed by a blank line,
      then the board sections with a blank line preceding each "[Board" line.
    - Save these new files in a nested folder, e.g. "{num_boards}-Board Sets/Source/".
    
    The new filename format is:
        "{base_name} Set {set_number} Hands {start}-{finish}.pbn"
    If the last subset file contains fewer than num_boards boards,
    append " (1 board)" or " (n boards)" before the file extension.
    """
    cwd = os.getcwd()
    
    # Loop through each subfolder in alphabetical order.
    for subfolder in sorted(os.listdir(cwd)):
        subfolder_path = os.path.join(cwd, subfolder)
        if not os.path.isdir(subfolder_path):
            continue
        
        # Look for an "All" folder in the subfolder.
        all_folder = os.path.join(subfolder_path, "All")
        if not os.path.isdir(all_folder):
            continue
        
        # Find the first .pbn file (case insensitive) in the "All" folder.
        pbn_files = sorted(f for f in os.listdir(all_folder) if f.lower().endswith('.pbn'))
        if not pbn_files:
            print(f"No .pbn file found in {all_folder}")
            continue
        
        pbn_file = pbn_files[0]
        base_name = os.path.splitext(pbn_file)[0]  # get the base filename without extension
        pbn_file_path = os.path.join(all_folder, pbn_file)
        
        with open(pbn_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the first occurrence of "[Board" to separate the preamble.
        board_index = content.find("[Board")
        if board_index == -1:
            print(f"No board sections found in file {pbn_file_path}")
            continue
        
        preamble = content[:board_index].rstrip()
        boards_content = content[board_index:]
        
        # Split the boards using a regex lookahead that retains "[Board" at the start of each section.
        boards = re.split(r'(?=\[Board)', boards_content)
        boards = [b.strip() for b in boards if b.strip()]
        
        # Create the nested folder for the board sets: e.g. "4-Board Sets/Source"
        subset_folder_path = os.path.join(subfolder_path, f"{num_boards}-Board Sets", "Source")
        os.makedirs(subset_folder_path, exist_ok=True)
        
        total_boards = len(boards)
        set_count = (total_boards + num_boards - 1) // num_boards  # ceiling division
        
        for set_index in range(set_count):
            start_index = set_index * num_boards
            end_index = start_index + num_boards
            subset_boards = boards[start_index:end_index]
            
            if not subset_boards:
                break  # no more boards to process
            
            # Board numbering is 1-indexed.
            start_board_number = start_index + 1
            finish_board_number = start_index + len(subset_boards)
            
            # If this set has fewer boards than num_boards, prepare an extra note.
            extra = ""
            if len(subset_boards) < num_boards:
                extra = f" ({len(subset_boards)} board{'s' if len(subset_boards) != 1 else ''})"
            
            # Construct the filename using the base name from the pbn file.
            file_name = f"{base_name} Set {set_index + 1} Hands {start_board_number}-{finish_board_number}{extra}.pbn"
            subset_file_path = os.path.join(subset_folder_path, file_name)
            
            # Write the new file: preamble plus a blank line and then the board subset.
            with open(subset_file_path, 'w', encoding='utf-8') as out_f:
                out_f.write(preamble + "\n\n" + "\n\n".join(subset_boards))
            
            print(f"Created file: {subset_file_path}")

if __name__ == "__main__":
    # Change the parameter here to 4 or 5 for different board sets.
    create_board_subsets(4)
    create_board_subsets(5)
    create_board_subsets(6)