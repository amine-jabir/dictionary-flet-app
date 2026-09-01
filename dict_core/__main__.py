"""
dict_core CLI entry point.
Invokes the production command-line interface.
"""

import sys
from dict_core.cli import main

if __name__ == "__main__":
    sys.exit(main())
