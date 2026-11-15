"""Stage 6 - Generate probability and ordinal hazard-intensity maps."""
from mapping_config import MAP_CONFIG
from volcanic_toolbox.postprocessing.mapping import run_probability_mapping
if __name__ == '__main__':
    run_probability_mapping(MAP_CONFIG)
