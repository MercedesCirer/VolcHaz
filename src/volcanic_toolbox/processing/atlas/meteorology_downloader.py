# -*- coding: utf-8 -*-
"""Download ERA5 as GRIB, validate it, then convert it to ATLAS NetCDF.

The final NetCDF names remain stable and are the files intended for ATLAS.
Raw GRIB files are transport/intermediate files and may be deleted after a
successful conversion.
"""
from __future__ import annotations
import json, logging, os, shutil, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence
import pandas as pd
try:
    import cdsapi
except ImportError:
    cdsapi=None
try:
    import netCDF4
except ImportError:
    netCDF4=None

PRESSURE_LEVELS=["1","2","3","5","7","10","20","30","50","70","100","125","150","175","200","225","250","300","350","400","450","500","550","600","650","700","750","775","800","825","850","875","900","925","950","975","1000"]
PRESSURE_VARIABLES=["geopotential","relative_humidity","temperature","u_component_of_wind","v_component_of_wind","vertical_velocity"]
SINGLE_LEVEL_VARIABLES=["10m_u_component_of_wind","10m_v_component_of_wind","2m_temperature","boundary_layer_height","geopotential","land_sea_mask"]
HOURS=[f"{h:02d}:00" for h in range(24)]

@dataclass(frozen=True)
class DateGroup:
    dates: tuple[datetime,...]
    @property
    def start(self): return self.dates[0]
    @property
    def end(self): return self.dates[-1]
    @property
    def label(self): return f"{self.start:%Y%m%d}_to_{self.end:%Y%m%d}"

@dataclass(frozen=True)
class DownloadJob:
    phase: str
    initial_date: datetime
    group: DateGroup
    area: tuple[float,float,float,float]
    target_folder: Path
    @property
    def job_id(self): return f"{self.phase}__{self.initial_date:%Y%m%d}__{self.group.label}"

class DownloadError(RuntimeError): pass


def read_scenario_table(path: Path)->pd.DataFrame:
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(path)
    if path.suffix.lower()=='.csv': table=pd.read_csv(path)
    elif path.suffix.lower() in {'.xlsx','.xls'}: table=pd.read_excel(path)
    else: raise ValueError('Scenario table must be CSV, XLSX or XLS')
    if table.empty: raise ValueError('Scenario table is empty')
    return table


def detect_phase_names(table, explicit_phase_names=None):
    phases=[str(x).strip() for x in explicit_phase_names] if explicit_phase_names else sorted({c[:-len('_column_height_m')] for c in table.columns if c.endswith('_column_height_m')})
    if not phases: raise ValueError("No phases detected from '*_column_height_m'")
    missing=[f'{p}_datetime' for p in phases if f'{p}_datetime' not in table]
    if missing: raise KeyError(f'Missing phase datetime columns: {missing}')
    return phases


def _accepted_mask(series):
    if series.dtype==bool: return series
    return series.astype(str).str.strip().str.lower().map({'true':True,'false':False,'1':True,'0':False}).fillna(False)


def build_scenario_phase_manifest(table, phase_names, accepted_only=True):
    source=table.copy()
    if accepted_only and 'accepted' in source: source=source.loc[_accepted_mask(source['accepted'])].copy()
    if source.empty: raise ValueError('No scenarios remain after acceptance filtering')
    if 'scenario_id' not in source: source.insert(0,'scenario_id',[f'scenario_{i:06d}' for i in range(1,len(source)+1)])
    records=[]
    for row_index,row in source.iterrows():
        for phase in phase_names:
            col=f'{phase}_datetime'; dt=pd.to_datetime(row[col],errors='coerce',utc=True)
            if pd.isna(dt): raise ValueError(f'Invalid datetime row={row_index}, column={col}: {row[col]!r}')
            records.append({'scenario_id':str(row['scenario_id']),'source_row':int(row_index),'phase':phase,'phase_datetime':dt.isoformat(),'initial_date':dt.strftime('%Y-%m-%d'),'initial_hour_utc':int(dt.hour),'date_key':dt.strftime('%Y%m%d'),'era5_folder':f'{phase}/date_{dt:%Y%m%d}'})
    manifest=pd.DataFrame(records).sort_values(['phase','initial_date','initial_hour_utc','scenario_id']).reset_index(drop=True)
    expected=len(source)*len(phase_names)
    if len(manifest)!=expected: raise RuntimeError(f'Incomplete manifest: expected {expected}, obtained {len(manifest)}')
    return manifest


def validate_area(area):
    if len(area)!=4: raise ValueError('Area order: NORTH WEST SOUTH EAST')
    n,w,s,e=map(float,area)
    if not (-90<=s<=n<=90): raise ValueError('Invalid latitude bounds')
    if not (-180<=w<e<=180): raise ValueError('Invalid longitude bounds')
    return n,w,s,e


def split_window_by_month(initial_date,days_after=10):
    if days_after<0: raise ValueError('days_after must be >=0')
    dates=[initial_date+timedelta(days=i) for i in range(days_after+1)]
    groups=[]
    for d in dates:
        if not groups or (d.year,d.month)!=(groups[-1][-1].year,groups[-1][-1].month): groups.append([d])
        else: groups[-1].append(d)
    return [DateGroup(tuple(g)) for g in groups]


def _base_request(group,area):
    return {'product_type':['reanalysis'],'year':[f'{group.start.year:04d}'],'month':[f'{group.start.month:02d}'],'day':[f'{d.day:02d}' for d in group.dates],'time':HOURS,'data_format':'grib','download_format':'unarchived','area':list(area)}

def build_pressure_request(group,area):
    r=_base_request(group,area); r.update({'variable':PRESSURE_VARIABLES,'pressure_level':PRESSURE_LEVELS}); return r

def build_single_level_request(group,area):
    r=_base_request(group,area); r.update({'variable':SINGLE_LEVEL_VARIABLES}); return r


def grib_file_is_usable(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size<16: return False
    with path.open('rb') as f: return f.read(4)==b'GRIB'


def netcdf_file_is_usable(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size<1024: return False
    with path.open('rb') as f: sig=f.read(8)
    if not (sig.startswith(b'CDF') or sig.startswith(b'\x89HDF')): return False
    if netCDF4 is not None:
        try:
            with netCDF4.Dataset(path) as ds:
                return bool(ds.variables)
        except Exception:
            return False
    return True


def retrieve_grib(client,dataset,request,target,overwrite=False):
    target=Path(target)
    if grib_file_is_usable(target) and not overwrite: return f'SKIP GRIB {target}'
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.part'); tmp.unlink(missing_ok=True)
    try:
        logging.info('Downloading GRIB %s -> %s',dataset,target)
        client.retrieve(dataset,request,str(tmp))
        if not grib_file_is_usable(tmp):
            raise DownloadError(f'Downloaded file does not have a GRIB signature: {tmp}')
        os.replace(tmp,target); return f'OK GRIB {target}'
    except Exception:
        tmp.unlink(missing_ok=True); raise


def convert_grib_to_netcdf(grib_path,netcdf_path,*,executable='grib_to_netcdf',data_type='NC_FLOAT',kind=3,compression_level=4,overwrite=False):
    grib_path,netcdf_path=Path(grib_path),Path(netcdf_path)
    if netcdf_file_is_usable(netcdf_path) and not overwrite: return f'SKIP NETCDF {netcdf_path}'
    if not grib_file_is_usable(grib_path): raise DownloadError(f'Cannot convert invalid GRIB: {grib_path}')
    exe=shutil.which(executable)
    if exe is None:
        raise ImportError("The ecCodes command 'grib_to_netcdf' was not found. In conda install it with: conda install -c conda-forge eccodes")
    netcdf_path.parent.mkdir(parents=True,exist_ok=True)
    tmp=netcdf_path.with_suffix(netcdf_path.suffix+'.part'); tmp.unlink(missing_ok=True)
    cmd=[exe,'-D',data_type,'-k',str(kind)]
    if compression_level and kind in {3,4}: cmd += ['-d',str(compression_level),' -s'] if False else ['-d',str(compression_level),'-s']
    cmd += ['-o',str(tmp),str(grib_path)]
    proc=subprocess.run(cmd,text=True,capture_output=True)
    if proc.returncode!=0:
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"GRIB-to-NetCDF conversion failed for {grib_path}\nCOMMAND: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    if not netcdf_file_is_usable(tmp):
        tmp.unlink(missing_ok=True); raise DownloadError(f'Converter did not create a usable NetCDF: {netcdf_path}')
    os.replace(tmp,netcdf_path); return f'OK NETCDF {netcdf_path}'


def build_jobs(manifest,area,output_dir,days_after):
    required={'phase','initial_date'}; missing=required.difference(manifest.columns)
    if missing: raise KeyError(f'Manifest missing: {sorted(missing)}')
    jobs=[]
    pairs=manifest[['phase','initial_date']].drop_duplicates().sort_values(['phase','initial_date'])
    for r in pairs.itertuples(index=False):
        dt=datetime.strptime(str(r.initial_date),'%Y-%m-%d'); folder=Path(output_dir)/str(r.phase)/f'date_{dt:%Y%m%d}'
        for group in split_window_by_month(dt,days_after): jobs.append(DownloadJob(str(r.phase),dt,group,area,folder))
    expected=sum(len(split_window_by_month(datetime.strptime(str(r.initial_date),'%Y-%m-%d'),days_after)) for r in pairs.itertuples(index=False))
    if len(jobs)!=expected: raise RuntimeError(f'Incomplete job construction: expected {expected}, got {len(jobs)}')
    return jobs


def _artifact_rows(job):
    rows=[]
    for product,dataset,request_builder in [('pressure','reanalysis-era5-pressure-levels',build_pressure_request),('single','reanalysis-era5-single-levels',build_single_level_request)]:
        stem=f'{product}_{job.group.label}'
        rows.append({'job_id':job.job_id,'phase':job.phase,'initial_date':job.initial_date.strftime('%Y-%m-%d'),'date_group':job.group.label,'number_of_days':len(job.group.dates),'product':product,'dataset':dataset,'raw_grib_path':str(job.target_folder/f'{stem}.grib'),'final_netcdf_path':str(job.target_folder/f'{stem}.nc'),'request':request_builder(job.group,job.area)})
    return rows


def build_download_plan(jobs):
    rows=[]
    for job in jobs: rows.extend(_artifact_rows(job))
    plan=pd.DataFrame([{k:v for k,v in r.items() if k!='request'} for r in rows])
    if len(plan)!=2*len(jobs): raise RuntimeError('Every monthly job must generate exactly pressure + single requests')
    return plan


def write_request_preview(jobs,output_dir):
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    for job in jobs:
        arts=_artifact_rows(job)
        records.append({'job_id':job.job_id,'phase':job.phase,'initial_date':job.initial_date.strftime('%Y-%m-%d'),'target_folder':str(job.target_folder),'date_group':job.group.label,'artifacts':[
            {'product':a['product'],'dataset':a['dataset'],'raw_grib_path':a['raw_grib_path'],'final_netcdf_path':a['final_netcdf_path'],'request':a['request']} for a in arts]})
    path=output_dir/'atlas_era5_request_preview.json'; path.write_text(json.dumps(records,indent=2),encoding='utf-8'); return path


def write_download_plan(jobs,output_dir):
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    plan=build_download_plan(jobs); path=output_dir/'atlas_era5_download_plan.csv'; plan.to_csv(path,index=False); return path,plan


def write_coverage_summary(manifest,jobs,plan,output_dir):
    rows=[]
    for phase,g in manifest.groupby('phase',sort=True):
        phase_jobs=[j for j in jobs if j.phase==phase]
        rows.append({'phase':phase,'scenario_phase_rows':len(g),'unique_phase_datetimes':g['phase_datetime'].nunique(),'unique_phase_dates':g['initial_date'].nunique(),'monthly_date_groups':len(phase_jobs),'pressure_requests':int(((plan.phase==phase)&(plan['product']=='pressure')).sum()),'single_requests':int(((plan.phase==phase)&(plan['product']=='single')).sum()),'total_file_requests':int((plan.phase==phase).sum())})
    summary=pd.DataFrame(rows)
    total=pd.DataFrame([{'phase':'__TOTAL__','scenario_phase_rows':len(manifest),'unique_phase_datetimes':manifest[['phase','phase_datetime']].drop_duplicates().shape[0],'unique_phase_dates':manifest[['phase','initial_date']].drop_duplicates().shape[0],'monthly_date_groups':len(jobs),'pressure_requests':int((plan['product']=='pressure').sum()),'single_requests':int((plan['product']=='single').sum()),'total_file_requests':len(plan)}])
    summary=pd.concat([summary,total],ignore_index=True); path=Path(output_dir)/'atlas_era5_coverage_summary.csv'; summary.to_csv(path,index=False); return path,summary


def download_job(job,*,overwrite=False,keep_grib=False,executable='grib_to_netcdf',data_type='NC_FLOAT',kind=3,compression_level=4):
    if cdsapi is None: raise ImportError('cdsapi is required: python -m pip install -e ".[era5]"')
    client=cdsapi.Client(); messages=[]
    products=[('pressure','reanalysis-era5-pressure-levels',build_pressure_request),('single','reanalysis-era5-single-levels',build_single_level_request)]
    for product,dataset,builder in products:
        stem=f'{product}_{job.group.label}'; grib=job.target_folder/f'{stem}.grib'; nc=job.target_folder/f'{stem}.nc'
        # A valid final NetCDF is authoritative; no redownload required.
        if netcdf_file_is_usable(nc) and not overwrite:
            messages.append(f'SKIP COMPLETE {nc}'); continue
        messages.append(retrieve_grib(client,dataset,builder(job.group,job.area),grib,overwrite))
        messages.append(convert_grib_to_netcdf(grib,nc,executable=executable,data_type=data_type,kind=kind,compression_level=compression_level,overwrite=overwrite))
        if not keep_grib and netcdf_file_is_usable(nc): grib.unlink(missing_ok=True); messages.append(f'REMOVED GRIB {grib}')
    return messages


def run_downloads(jobs,*,max_workers,overwrite,keep_grib,executable,data_type,kind,compression_level,failed_log):
    failures=[]; total=len(jobs)
    if max_workers<1: raise ValueError('max_workers must be >=1')
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures={pool.submit(download_job,j,overwrite=overwrite,keep_grib=keep_grib,executable=executable,data_type=data_type,kind=kind,compression_level=compression_level):j for j in jobs}
        for completed,fut in enumerate(as_completed(futures),1):
            j=futures[fut]
            try:
                for msg in fut.result(): logging.info('[%d/%d] %s',completed,total,msg)
            except Exception as e:
                desc=f'{j.phase} | {j.initial_date:%Y-%m-%d} | {j.group.label} | {type(e).__name__}: {e}'; failures.append(desc); logging.error('[%d/%d] FAILED %s',completed,total,desc)
    if failures:
        failed_log=Path(failed_log); failed_log.parent.mkdir(parents=True,exist_ok=True); failed_log.write_text('\n\n'.join(failures)+'\n',encoding='utf-8'); raise DownloadError(f'{len(failures)} jobs failed; see {failed_log}')
    Path(failed_log).unlink(missing_ok=True)
