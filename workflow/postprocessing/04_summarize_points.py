from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "workflow")]
from volcanic_toolbox.example_workflows.runtime import execute
if __name__ == "__main__":
    execute('16_summarize_point_hazard', globals(), ROOT / "workflow")
