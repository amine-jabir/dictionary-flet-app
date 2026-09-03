"""
Setup script for packaging dictionary-app.
"""

from setuptools import find_packages, setup

setup(
    name="dictionary-app",
    version="1.0.1",
    description="Cross-platform English dictionary application with offline lexicon, audio playback, and reactive Flet UI.",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Dictionary Project Team",
    packages=find_packages(include=["dict_core*", "dict_client_flet*"]),
    package_data={
        "": ["*.db", "*.json", "*.txt"],
    },
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.28.0",
        "flet>=0.21.0",
    ],
    entry_points={
        "console_scripts": [
            "dict-cli = dict_core.cli:main",
            "dict-gui = dict_client_flet.main:run",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
