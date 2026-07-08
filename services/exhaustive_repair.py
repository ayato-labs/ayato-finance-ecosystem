import subprocess
import os
from pathlib import Path

# Finance root directory
ROOT_DIR = Path(__file__).resolve().parents[1]
SERVICES_DIR = ROOT_DIR / "services"

services = [d for d in SERVICES_DIR.iterdir() if d.is_dir()]

print(f"Starting exhaustive environment repair for {len(services)} services...")

# We clear VIRTUAL_ENV to ensure uv targets the local .venv of each service
env = os.environ.copy()
if "VIRTUAL_ENV" in env:
    del env["VIRTUAL_ENV"]

for service in services:
    pyproject = service / "pyproject.toml"
    if pyproject.exists():
        print(f"\n--- Repairing {service.name} ---")
        try:
            # Reinstall all packages to ensure integrity
            subprocess.run(
                ["uv", "sync", "--reinstall"], cwd=str(service), check=True, env=env
            )
            print(f"SUCCESS: {service.name} environment repaired.")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to repair {service.name}: {e}")

print("\nAll repairs attempted.")
