from pathlib import Path
import sys
import runpy
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"workflow")]
from volcanic_toolbox.example_workflows.runtime import load_settings

if __name__=="__main__":
    options=load_settings(ROOT/"workflow/preprocessing/configs/preprocessing_config.py")
    steps=[]
    if options["RUN_PREVIEW"] or options["RUN_PARAMETER_COMPARISON"]: steps.append("01_preview_eruption")
    if options["DOWNLOAD_METEOROLOGY"]: steps.append("02_download_meteorology")
    steps.extend(["03_prepare_meteorology","04_sample_meteorology"])
    if options["RUN_WIND_ROSES"]: steps.append("05_wind_roses")
    steps.append("06_build_scenarios")
    if options["RUN_SCENARIO_PLOTS"]: steps.append("07_check_scenarios")
    if options["RUN_WIND_COMPARISON"]: steps.append("08_compare_winds")
    if options["RUN_PARAMETER_COMPARISON"]: steps.append("09_compare_parameters")
    for step in steps:
        print(f"\nRunning: {step}")
        runpy.run_path(str(Path(__file__).parent/(step+".py")),run_name="__main__")
