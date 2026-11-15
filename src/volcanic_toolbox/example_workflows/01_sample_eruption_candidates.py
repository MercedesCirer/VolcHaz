"""Sample stochastic eruptive-parameter candidates and inspect their distributions.

This example performs the first eruptive-source preprocessing step.

For every eruptive phase defined in ``scenario_config.py`` it:

1. Samples an unvalidated candidate population from the configured stochastic
   eruptive parameters.
2. Saves the complete candidate table.
3. Calculates and saves descriptive statistics.
4. Creates one diagnostic distribution figure for every configured parameter.

IMPORTANT
---------
The candidate population generated here is NOT yet a physically validated
eruption ensemble.

At this stage, parameters are sampled only from the probability distributions
and bounds defined by the user. Physical consistency is evaluated later, after
the eruptive candidates are coupled with meteorological conditions and MER,
erupted mass, and VEI constraints are applied.

The distribution figures are therefore intended to inspect the INPUT
uncertainty assigned to each parameter. They are complementary to the later
accepted/rejected pairplots, which show how physical validation modifies the
sampled parameter space.
"""
from pathlib import Path
import matplotlib.pyplot as plt
from volcanic_toolbox.preprocessing.eruption import sample_candidate_eruption_parameters, summarize_samples
from volcanic_toolbox.preprocessing.output import ScenarioOutputManager
from volcanic_toolbox.preprocessing.plotting import plot_parameter_histogram
from scenario_config import SCENARIO_NAME, phase_configs
NUMBER_OF_CANDIDATES = 1000
RANDOM_SEED = 42
HISTOGRAM_BINS = 30
HISTOGRAM_DENSITY = True
OVERLAY_THEORETICAL_PDF = True
SHOW_FIGURES = False

def main():
    phases = tuple(phase_configs())
    if not phases:
        raise ValueError('scenario_config.phase_configs() returned no eruptive phases.')
    outputs = ScenarioOutputManager(scenario_name=SCENARIO_NAME).ensure([phase.name for phase in phases])
    distribution_root = outputs.figures_dir / 'eruption_distributions'
    distribution_root.mkdir(parents=True, exist_ok=True)
    print('=' * 79)
    print('ERUPTIVE PARAMETER CANDIDATE SAMPLING')
    print('=' * 79)
    print(f'Scenario: {SCENARIO_NAME}')
    print('Phases:   ' + ', '.join((phase.name for phase in phases)))
    print(f'Candidates per phase: {NUMBER_OF_CANDIDATES:,}')
    print()
    for phase_index, phase in enumerate(phases):
        phase_seed = RANDOM_SEED + phase_index
        table = sample_candidate_eruption_parameters(parameters=phase.parameters, number_of_candidates=NUMBER_OF_CANDIDATES, seed=phase_seed, candidate_prefix=phase.name)
        candidate_path = outputs.eruption_dir / f'{phase.name}_candidates.csv'
        table.to_csv(candidate_path, index=False)
        summary = summarize_samples(table)
        summary_path = outputs.eruption_dir / f'{phase.name}_summary.csv'
        summary.to_csv(summary_path, index=False)
        phase_figure_dir = distribution_root / phase.name
        phase_figure_dir.mkdir(parents=True, exist_ok=True)
        print(f'[{phase.name}] {len(table):,} unvalidated candidates')
        print(f'  Candidates: {candidate_path}')
        print(f'  Summary:    {summary_path}')
        for parameter in phase.parameters:
            column = parameter.column_name
            if column not in table.columns:
                raise KeyError(f"Expected sampled column '{column}' for parameter '{parameter.key}' in phase '{phase.name}'.")
            figure_path = phase_figure_dir / f'{parameter.key}_distribution.png'
            fig, _ = plot_parameter_histogram(values=table[column].to_numpy(), config=parameter, bins=HISTOGRAM_BINS, density=HISTOGRAM_DENSITY, overlay_pdf=OVERLAY_THEORETICAL_PDF, output_path=figure_path, show=SHOW_FIGURES)
            if not SHOW_FIGURES:
                plt.close(fig)
            print(f'  Figure:     {figure_path}')
        print()
    print('=' * 79)
    print('ERUPTIVE PARAMETER PREVIEW COMPLETED')
    print('=' * 79)
    print()
    print('These samples remain UNVALIDATED. Physical validation occurs later after meteorological coupling.')
if __name__ == '__main__':
    main()
