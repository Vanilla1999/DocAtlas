import json
import os
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from docmancer._version import __version__

ROOT = Path(__file__).resolve().parents[1]



