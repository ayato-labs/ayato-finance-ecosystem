import os

def find_ambiguous(root_dir):
    ambiguous_chars = ["（", "）", "：", "；", "！", "？", "，", "．", "　", "－", "’", "”"]
    for root, dirs, files in os.walk(root_dir):
        if any(skip in root for skip in [".git", ".venv", "__pycache__", ".ruff_cache"]):
            continue
        for file in files:
            if file.endswith(".py") or file.endswith(".md"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        for char in ambiguous_chars:
                            if char in content:
                                print(f"MATCH: {char} in {path}")
                                break
                except:
                    pass

if __name__ == "__main__":
    find_ambiguous(".")
