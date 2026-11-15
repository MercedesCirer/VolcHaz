"""Run complete ATLAS Stage 5 postprocessing."""
from volcanic_toolbox.postprocessing import run_atlas_postprocessing
from postprocessing_config import ATLAS_INDEX_CONFIG, ATLAS_POSTPROCESS_CONFIG
manifest = run_atlas_postprocessing(ATLAS_POSTPROCESS_CONFIG, index_config=ATLAS_INDEX_CONFIG)
print('\nStage 5 completed.')
print(manifest.to_string(index=False))
