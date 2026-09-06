"""
Confluence Backend Package
Unified Coastal Environmental Intelligence Platform
"""

import sys
import os

# Automatically ensure backend modules are discoverable when package is imported
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

__version__ = "2.0.0"
