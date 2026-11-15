"""Command-line menu for the three-stage volcanic-hazard workflow."""
from pathlib import Path
import argparse
import runpy
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"workflow")]
from volcanic_toolbox.example_workflows.runtime import validate_configuration

def main():
    parser=argparse.ArgumentParser(description="VolcHaz: select a workflow stage and step")
    parser.add_argument("stage",nargs="?",choices=["preprocessing","processing","postprocessing"])
    parser.add_argument("step",nargs="?",help="Step number, or all to run the main sequence")
    parser.add_argument("--check",action="store_true",help="Validate settings without downloading data or running the model")
    args=parser.parse_args()
    if args.check:
        try:
            summary=validate_configuration(ROOT/"workflow")
        except (ValueError, TypeError, KeyError, FileNotFoundError) as error:
            parser.exit(1,f"Configuration error: {error}\n")
        print(f"Valid configuration: {summary['scenario_name']}, {summary['phase_count']} phase(s)")
        return
    stage=args.stage
    if stage is None:
        options=["preprocessing","processing","postprocessing"]
        print("1. Preprocessing: prepare eruption scenarios\n2. Processing: run ATLAS\n3. Postprocessing: analyze model outputs")
        answer=input("Stage (1-3): ").strip()
        if answer not in {"1","2","3"}: parser.error("Select 1, 2, or 3")
        stage=options[int(answer)-1]
    scripts=sorted((ROOT/"workflow"/stage).glob("[0-9]*.py"))
    for script in scripts: print(script.stem)
    print("all: run the main sequence")
    step=args.step or input("Step: ").strip()
    if step=="all": path=ROOT/"workflow"/stage/"run_all.py"
    else:
        candidates=[p for p in scripts if p.stem.split("_")[0]==step.zfill(2) or p.stem==step]
        if len(candidates)!=1: parser.error("Unknown step")
        path=candidates[0]
    try:
        runpy.run_path(str(path),run_name="__main__")
    except (FileNotFoundError,ValueError,TypeError,KeyError) as error:
        parser.exit(1,f"\nThe step could not be completed: {error}\n")

if __name__=="__main__": main()
