import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

def main():
    from Celica_Toolworks import run_app

    run_app()

if __name__ == "__main__":
    main()
