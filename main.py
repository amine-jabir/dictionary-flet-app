"""
Root entry point for Flet packaging and execution (Desktop, Mobile, Web).
Used by 'flet run', 'flet build apk', 'flet build web', 'flet build ipa', and 'python main.py'.
"""

import sys
from dict_client_flet.main import run

if __name__ == "__main__":
    run()
