import os
import sys

# 置換対象の文字マッピング (Unicodeエスケープを使用して環境依存を回避)
REPLACEMENTS = {
    "\uff08": "(",  # （
    "\uff09": ")",  # ）
    "\uff1a": ":",  # ：
    "\uff1b": ";",  # ；
    "\uff01": "!",  # ！
    "\uff1f": "?",  # ？
    "\uff0c": ",",  # ，
    "\uff0e": ".",  # ．
    "\u3000": " ",  # 全角スペース
    "\uff0d": "-",  # －
}

# 対象とするファイル拡張子
TARGET_EXTENSIONS = {".py", ".md"}

# スキップするディレクトリ
SKIP_DIRS = {".git", ".venv", ".venv_new", "__pycache__", ".ruff_cache", ".pytest_cache", "node_modules", "site-packages", "venv"}

def fix_file(file_path):
    try:
        # UTF-8で読み込み
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        new_content = content
        for char_code, replacement in REPLACEMENTS.items():
            # unicode_escape を使って実際の文字に変換
            char = char_code.encode().decode('unicode_escape') if '\\' in char_code else char_code
            if char in content:
                # print(f"  [Found {char_code}] in {file_path}")
                new_content = new_content.replace(char, replacement)
        
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Fixed: {file_path}")
            return True
    except UnicodeDecodeError:
        # UTF-8で読めない場合はスキップ（バイナリ等）
        pass
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return False

def main():
    if len(sys.argv) > 1:
        root_dir = os.path.abspath(sys.argv[1])
    else:
        root_dir = os.getcwd()
    
    print(f"Scanning from: {root_dir}")
    
    fixed_count = 0
    for root, dirs, files in os.walk(root_dir):
        # スキップ対象ディレクトリを除外
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        
        for file in files:
            if any(file.endswith(ext) for ext in TARGET_EXTENSIONS):
                file_path = os.path.join(root, file)
                if fix_file(file_path):
                    fixed_count += 1
    
    print(f"\nDone! Fixed {fixed_count} files.")

if __name__ == "__main__":
    main()
