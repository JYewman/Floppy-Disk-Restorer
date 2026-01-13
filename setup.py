#!/usr/bin/env python3
"""
Compatibility shim for pip install -e .

This allows standard pip editable installs to work alongside poetry.
For full dependency management, use poetry install.
"""

from setuptools import setup, find_packages

setup(
    name="floppy-workbench",
    version="2.0.0",
    description="Professional floppy disk analysis and recovery tool using Greaseweazle V4.1",
    author="Joshua Yewman",
    author_email="joshua@yewman.co.uk",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "PyQt6>=6.6.0",
        "PyQt6-Charts>=6.6.0",
        "pydantic>=2.5.0",
        "rich>=13.7.0",
        "numpy>=1.26.0",
        "reportlab>=4.0.0",
    ],
    extras_require={
        "charts": ["pyqtgraph>=0.13.0"],
    },
    entry_points={
        "console_scripts": [
            "floppy-workbench=floppy_formatter.main:main",
            "floppy-format=floppy_formatter.main:main",
        ],
    },
)
