"""
Direct CLI launcher for the Dictionary application.
Usage: python run_cli.py lookup <word>
       python run_cli.py interactive
"""

import sys
from dict_core.cli import main

if __name__ == "__main__":
    sys.exit(main())
