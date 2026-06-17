import sys
import os

# Set project root in sys.path for proper module imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import and execute the main Streamlit application
import ui.app
