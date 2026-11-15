# Internal compatibility bridge. Edit workflow/postprocessing/configs/postprocessing_config.py instead.
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from volcanic_toolbox.example_workflows.runtime import execute, resolve_examples
execute('mapping_config', globals(), resolve_examples(ROOT / "workflow"))
