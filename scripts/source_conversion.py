import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        self.load_logic()

    def load_logic(self):
        """Loads all rules from source_logic*.txt files."""
        logic_files = glob.glob(os.path.join(self.logic_dir, "source_logic*.txt"))
        for logic_file in logic_files:
            with open(logic_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        # Format: name|search|replace
                        parts = line.strip().split('|')
                        if len(parts) == 3:
                            self.rules.append({
                                "name": parts[0],
                                "search": parts[1],
                                "replace": parts[2]
                            })
        print(f"Loaded {len(self.rules)} logic rules.")

    def apply_logic(self, file_path):
        """Applies loaded rules to a single file."""
        with open(file_path, 'r') as f:
            content = f.read()

        original_content = content
        for rule in self.rules:
            try:
                content = re.sub(rule['search'], rule['replace'], content)
            except Exception as e:
                print(f"Error applying rule '{rule['name']}' on {file_path}: {e}")

        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            return True
        return False

if __name__ == "__main__":
    # Example usage for the driver
    converter = SourceConverter()
    # You can loop through your src directory here
