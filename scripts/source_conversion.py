import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []

    def load_logic(self, level):
        """Loads rules specifically for the current intelligence level."""
        self.rules = []
        # Looks for files like source_logic_level1.txt
        pattern = os.path.join(self.logic_dir, f"source_logic_level{level}.txt")
        logic_files = glob.glob(pattern)
        
        for logic_file in logic_files:
            with open(logic_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Format: name|search|replace
                        parts = line.split('|')
                        if len(parts) == 3:
                            self.rules.append({
                                "name": parts[0],
                                "search": parts[1],
                                "replace": parts[2]
                            })
        print(f"Loaded {len(self.rules)} rules for Level {level}.")

    def apply_to_file(self, file_path):
        """Applies loaded rules and returns number of changes made."""
        if not os.path.exists(file_path):
            return 0
            
        with open(file_path, 'r') as f:
            content = f.read()

        original_content = content
        changes_count = 0
        
        for rule in self.rules:
            new_content = re.sub(rule['search'], rule['replace'], content)
            if new_content != content:
                content = new_content
                changes_count += 1
                print(f"    ✨ Rule '{rule['name']}' applied to {os.path.basename(file_path)}")

        if changes_count > 0:
            with open(file_path, 'w') as f:
                f.write(content)
                
        return changes_count
