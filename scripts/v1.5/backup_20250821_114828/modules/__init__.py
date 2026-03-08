"""
DeFi Risk Assessment Script - Modular Structure
Version 1.4.1
"""

__version__ = "1.4.1"
__author__ = "DeFi Risk Assessment Team"
__description__ = "Modular DeFi Risk Assessment System"

# Import all modules for easy access
from .core import DeFiRiskAssessor
from .data_collectors import *
from .scorers import *
from .validators import *
from .utils import * 