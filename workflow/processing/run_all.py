from pathlib import Path
import runpy

if __name__ == "__main__":
    for step in ['01_prepare_model_meteorology', '03_build_model_inputs', '04_run_model']:
        print(f"\nRunning: {step}")
        runpy.run_path(str(Path(__file__).parent / (step + ".py")), run_name="__main__")
