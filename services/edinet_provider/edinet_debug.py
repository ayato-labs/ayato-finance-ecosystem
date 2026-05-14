import sys
from pathlib import Path

# Add site-packages to path just in case
site_packages = Path.cwd() / ".venv" / "Lib" / "site-packages"
sys.path.append(str(site_packages))

print("--- EDINET_TOOLS DEBUG START ---")

print("Importing edinet_tools.config...")
import edinet_tools.config
print("Importing edinet_tools.timezone...")
import edinet_tools.timezone
print("Importing edinet_tools.entity_classifier...")
import edinet_tools.entity_classifier
print("Importing edinet_tools.entity...")
import edinet_tools.entity
print("Importing edinet_tools.document...")
import edinet_tools.document
print("Importing edinet_tools.doc_types...")
import edinet_tools.doc_types
print("Importing edinet_tools.parsers...")
import edinet_tools.parsers
print("Importing edinet_tools._client...")
import edinet_tools._client

print("--- EDINET_TOOLS DEBUG END ---")
