from pathlib import Path
import runpy

if __name__ == "__main__":
    for step in ['01_compute_probabilities', '06_make_maps']:
        print(f"\nRunning: {step}")
        runpy.run_path(str(Path(__file__).parent / (step + ".py")), run_name="__main__")
