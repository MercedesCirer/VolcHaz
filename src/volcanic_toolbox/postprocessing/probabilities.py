"""Probability calculations and NetCDF output."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re, numpy as np
from netCDF4 import Dataset
from .atlas_reader import AtlasGrid, inspect, validate_grid, read_c3d, read_gl_final, AtlasOutputError

def token(x): return f"{float(x):.12g}".replace("-","m").replace(".","p").replace("+","")
def safe(x): return re.sub(r"[^A-Za-z0-9_]+","_",x).strip("_")
def compare(x,t,op): return x>t if op==">" else x>=t
def vertical(x,idx,op): return np.nanmax(x[:,idx],axis=1) if op=="maximum" else np.nanmean(x[:,idx],axis=1)
def first_and_run(mask):
    arrived=np.any(mask,axis=0); first=np.where(arrived,np.argmax(mask,axis=0),-1).astype(np.int32)
    run=np.zeros(first.shape,np.int32); alive=np.zeros(first.shape,bool)
    for t in range(mask.shape[0]):
        alive=np.where(first==t,True,alive); alive &= mask[t]; run += alive.astype(np.int32)
    return first,np.where(arrived,run,0)
@dataclass
class ProbabilityResult:
    phase:str; subset:str; grid:AtlasGrid; fields:dict; metadata:dict; valid_files:list; invalid_files:list

def calculate_probabilities(simulations,phase,subset,config):
    ref=None; valid=[]; names={}; invalid=[]
    for s in simulations:
        try:
            g,n=inspect(s.path)
            if ref is None: ref=g
            else: validate_grid(ref,g,s.path)
            valid.append(s); names[s.path]=n
        except Exception as e:
            invalid.append((s.path,str(e)))
            if not config.skip_invalid_files: raise
    if ref is None or not valid:
        details = "\n".join(
            f"  - {path}: {error}"
            for path, error in invalid[:5]
        )
        more = ""
        if len(invalid) > 5:
            more = f"\n  ... and {len(invalid) - 5} more invalid file(s)."
        raise AtlasOutputError(
            f"No valid outputs for {phase}/{subset}. "
            f"Discovered {len(simulations)} file(s), but all were rejected."
            + (f"\nFirst errors:\n{details}{more}" if details else "")
        )
    shape=(len(ref.lat),len(ref.lon)); fields={}; meta={}
    glc={th:np.zeros(shape,np.uint32) for th in config.gl_thresholds_kg_m2}; ngl=0
    for s in valid:
        try:
            with Dataset(s.path) as ds: gl=read_gl_final(ds,names[s.path])
            for th in glc: glc[th]+=compare(gl,th,config.probability_comparison).astype(np.uint32)
            ngl+=1
        except Exception as e:
            invalid.append((s.path,f"GL: {e}"))
            if not config.skip_invalid_files: raise
    for th,count in glc.items():
        if ngl:
            name=f"gl_poe_thr_{token(th)}_kg_m2"; fields[name]=count/ngl*100
            meta[name]={"metric":"ground_load_probability_of_exceedance","threshold":float(th),"threshold_units":"kg m-2","comparison":config.probability_comparison,"n_valid":ngl,"time_reduction":"final_time_record"}
    for altitude_range in config.altitude_ranges:
        idx=np.where((ref.alt>=altitude_range.minimum_m)&(ref.alt<=altitude_range.maximum_m))[0]
        if not len(idx): continue
        ccount={th:np.zeros(shape,np.uint32) for th in config.c3d_thresholds_kg_m3}
        acount={th:{h:np.zeros(shape,np.uint32) for h in config.arrival_hours} for th in config.c3d_thresholds_kg_m3}
        pcount={th:{h:np.zeros(shape,np.uint32) for h in config.persistence_hours} for th in config.c3d_thresholds_kg_m3}
        arrived_count={th:np.zeros(shape,np.uint32) for th in config.c3d_thresholds_kg_m3}; nc=0
        for s in valid:
            try:
                with Dataset(s.path) as ds: c3d=read_c3d(ds,names[s.path])
                exceed=vertical(c3d,idx,config.c3d_exceedance_vertical_operator); temporal=vertical(c3d,idx,config.temporal_vertical_operator)
                for th in config.c3d_thresholds_kg_m3:
                    ccount[th]+=np.any(compare(exceed,th,config.probability_comparison),axis=0).astype(np.uint32)
                    first,run=first_and_run(compare(temporal,th,config.probability_comparison)); arrived=first>=0; arrived_count[th]+=arrived.astype(np.uint32)
                    at=first*config.dt_hours; pt=run*config.dt_hours
                    for h in config.arrival_hours: acount[th][h]+=(arrived&(at<=h)).astype(np.uint32)
                    for h in config.persistence_hours: pcount[th][h]+=(arrived&(pt>=h)).astype(np.uint32)
                nc+=1
            except Exception as e:
                invalid.append((s.path,f"C3D: {e}"))
                if not config.skip_invalid_files: raise
        if not nc: continue
        range_token=safe(altitude_range.name)
        for th in config.c3d_thresholds_kg_m3:
            tt=token(th); name=f"c3d_poe_thr_{tt}_kg_m3_{range_token}"; fields[name]=ccount[th]/nc*100
            meta[name]={"metric":"c3d_probability_of_exceedance","threshold":float(th),"threshold_units":"kg m-3","altitude_range":altitude_range.name,"minimum_altitude_m":altitude_range.minimum_m,"maximum_altitude_m":altitude_range.maximum_m,"vertical_operator":config.c3d_exceedance_vertical_operator,"time_reduction":"any_time","n_valid":nc}
            for h in config.arrival_hours:
                name=f"arrival_poe_thr_{tt}_kg_m3_le_{token(h)}h_{range_token}"; fields[name]=acount[th][h]/nc*100
                meta[name]={"metric":"arrival_probability","definition":"P(AT <= t)","threshold":float(th),"threshold_units":"kg m-3","time_threshold_h":float(h),"altitude_range":altitude_range.name,"vertical_operator":config.temporal_vertical_operator,"n_valid":nc}
            den=arrived_count[th].astype(float); den=np.where(den>0,den,np.nan)
            for h in config.persistence_hours:
                if "unconditional" in config.persistence_outputs:
                    name=f"persistence_uncond_thr_{tt}_kg_m3_ge_{token(h)}h_{range_token}"; fields[name]=pcount[th][h]/nc*100
                    meta[name]={"metric":"post_arrival_persistence_probability","definition":"P(arrival and PT >= t)","conditioning":"unconditional","threshold":float(th),"threshold_units":"kg m-3","time_threshold_h":float(h),"altitude_range":altitude_range.name,"vertical_operator":config.temporal_vertical_operator,"n_valid":nc}
                if "conditional" in config.persistence_outputs:
                    name=f"persistence_cond_thr_{tt}_kg_m3_ge_{token(h)}h_{range_token}"; fields[name]=pcount[th][h]/den*100
                    meta[name]={"metric":"post_arrival_persistence_probability","definition":"P(PT >= t | arrival)","conditioning":"conditional_on_arrival","threshold":float(th),"threshold_units":"kg m-3","time_threshold_h":float(h),"altitude_range":altitude_range.name,"vertical_operator":config.temporal_vertical_operator,"n_valid":nc}
    return ProbabilityResult(phase,subset,ref,fields,meta,[s.path for s in valid],invalid)

def write_probability_netcdf(result,path):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp")
    with Dataset(tmp,"w",format="NETCDF4") as ds:
        ds.createDimension("lat",len(result.grid.lat)); ds.createDimension("lon",len(result.grid.lon))
        lat=ds.createVariable("lat","f8",("lat",)); lon=ds.createVariable("lon","f8",("lon",)); lat[:]=result.grid.lat; lon[:]=result.grid.lon; lat.units="degrees_north"; lon.units="degrees_east"
        ds.phase=result.phase; ds.subset=result.subset
        for name,values in result.fields.items():
            v=ds.createVariable(name,"f4",("lat","lon"),zlib=True,complevel=4,fill_value=np.float32(np.nan)); v[:]=values
            for k,val in result.metadata[name].items(): setattr(v,k,val)
    tmp.replace(path); return path
