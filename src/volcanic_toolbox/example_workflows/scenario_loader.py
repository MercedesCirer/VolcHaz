"""Convert scientific settings to validated domain objects."""
from volcanic_toolbox.preprocessing.eruption import BoundsConfig, ParameterConfig, EruptionPhaseConfig

def configure_scenario(settings):
    values=dict(settings)
    phase_data=values.pop("PHASES")
    phases=[]
    for entry in phase_data:
        entry=dict(entry)
        parameters=[]
        for parameter in entry.pop("parameters"):
            parameter=dict(parameter)
            if parameter.get("bounds") is not None:
                parameter["bounds"]=BoundsConfig(**parameter["bounds"])
            parameters.append(ParameterConfig(**parameter))
        phases.append(EruptionPhaseConfig(parameters=parameters,**entry))
    def validate():
        scenario_name=values["SCENARIO_NAME"]
        if not isinstance(scenario_name,str) or not scenario_name.strip() or scenario_name in {".",".."} or "/" in scenario_name or "\\" in scenario_name:
            raise ValueError("SCENARIO_NAME must be a nonempty folder name, not a path")
        if len(values["YEARS"])!=2 or any(not isinstance(y,int) or isinstance(y,bool) for y in values["YEARS"]):
            raise ValueError("YEARS must contain exactly two integer years")
        if values["TGSD_MIN_PHI"]>=values["TGSD_MAX_PHI"]:
            raise ValueError("TGSD_MIN_PHI must be below TGSD_MAX_PHI")
        kind=values["SCENARIO_TYPE"]
        if kind not in {"monophase","multiphase"}:
            raise ValueError("SCENARIO_TYPE must be monophase or multiphase")
        if (kind=="monophase" and len(phases)!=1) or (kind=="multiphase" and len(phases)<2):
            raise ValueError("The number of PHASES is inconsistent with SCENARIO_TYPE")
        names=[p.name for p in phases]
        if len(names)!=len(set(names)):
            raise ValueError("Phase names must be unique")
        if set(names)!=set(values["PHASE_METEOROLOGY"]):
            raise ValueError("PHASE_METEOROLOGY must contain the same phase names as PHASES")
        for name,weather in values["PHASE_METEOROLOGY"].items():
            if weather["source"] not in {"tmy","historical"} or weather["pressure_level_hpa"]<=0:
                raise ValueError(f"Invalid meteorological settings for {name}")
        if values["COLUMN_HEIGHT_REFERENCE"] not in {"asl","above_vent"}:
            raise ValueError("COLUMN_HEIGHT_REFERENCE must be asl or above_vent")
        for name,minimum,maximum in values.get("MULTIPHASE_MASS_FRACTION_CONSTRAINTS",()):
            if name not in names or not 0<=minimum<=maximum<=1:
                raise ValueError("Invalid phase mass-fraction constraint")
        if not -90<=values["LATITUDE"]<=90 or not -180<=values["LONGITUDE"]<=180:
            raise ValueError("Latitude or longitude is outside its valid range")
        if values["YEARS"][0]>values["YEARS"][1]:
            raise ValueError("The start year must not exceed the end year")
        if values["N_METEOROLOGY_SAMPLES"]<=0:
            raise ValueError("N_METEOROLOGY_SAMPLES must be positive")
    validate()
    values.update(phase_configs=lambda:list(phases),
                  phase_mass_fraction_constraints=lambda:values.get("MULTIPHASE_MASS_FRACTION_CONSTRAINTS",()),
                  validate_scenario_configuration=validate)
    return values
