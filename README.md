# VolcHaz

VolcHaz builds volcanic eruption scenarios from ERA5 data, prepares and runs ATLAS tephra-dispersal simulations, and estimates hazard from the resulting ensemble.

- [English user manual](docs/USER_MANUAL_EN.md)
- [Manual de usuario en español](docs/MANUAL_ES.md)
- [Configuration reference in English](workflow/CONFIGURATION.md)

The [workflow overview](workflow/README.md) links to the numbered scripts for each stage.

The three editable configuration files are in `workflow/<stage>/configs/`. Run `python workflow/run.py --check` from the repository root after installation to check all three.

`VolcHaz` is distributed under the [MIT License](LICENSE). ATLAS and external datasets are available from their own providers.
