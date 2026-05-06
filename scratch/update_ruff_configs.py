import os
import re

ignore_rules = 'ignore = ["PLR0913", "PLR0912", "PLR0915", "PLR2004", "PLC0415", "E402", "RUF001", "RUF002", "RUF003"]'

services_dir = r"c:\Users\saiha\My_Service\programing\finance\services"
for root, dirs, files in os.walk(services_dir):
    if "pyproject.toml" in files:
        path = os.path.join(root, "pyproject.toml")
        print(f"Updating {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace existing ignore or add it
        if 'ignore = [' in content:
            new_content = re.sub(r'ignore = \[.*?\]', ignore_rules, content)
        else:
            # Add to [tool.ruff.lint]
            new_content = content.replace('[tool.ruff.lint]', f'[tool.ruff.lint]\n{ignore_rules}')
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
