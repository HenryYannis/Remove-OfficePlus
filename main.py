import sys
import os

# Add src to python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from officeplus_nuker.cli import main

if __name__ == "__main__":
    main()
