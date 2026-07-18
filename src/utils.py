"""
Common utilities for notebooks and scripts.
"""

from pathlib import Path
import sys


def setup_project_path():
    """
    Add the project root (CPWpython) to sys.path.
    Works regardless of the current working directory.
    """

    project_root = Path(__file__).resolve().parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    return project_root