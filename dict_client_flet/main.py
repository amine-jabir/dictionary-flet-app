"""
Main launcher for the Flet desktop / mobile / web dictionary application.
"""

import flet as ft
from dict_client_flet.app import main_app


def run() -> None:
    """Launches the cross-platform Flet UI."""
    if hasattr(ft, "run"):
        ft.run(main_app)
    else:
        ft.app(target=main_app)


if __name__ == "__main__":
    run()
