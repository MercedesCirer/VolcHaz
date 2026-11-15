"""Optional SSH/MPI execution helper for ATLAS 1.0."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import os
from pathlib import Path, PurePosixPath
import shlex
import socket
import sys
import time
from datetime import datetime

import pandas as pd

try:
    import paramiko
except ImportError:
    paramiko = None


class AtlasRemoteError(RuntimeError):
    """Raised when a remote ATLAS operation cannot be completed safely."""


@dataclass(frozen=True)
class AtlasRemoteConfig:
    """Configuration for resumable SSH-based ATLAS execution.

    Passwords are not stored directly. ``password_env_var`` names the
    environment variable from which the password is read when required.
    """

    scenario_name: str
    local_inputs_root: Path | str
    local_meteorology_root: Path | str
    local_runs_root: Path | str
    ssh_host: str
    ssh_user: str
    ssh_port: int = 22
    phases: tuple[str, ...] | None = None
    password_env_var: str | None = "ATLAS_SSH_PASSWORD"
    private_key_path: Path | str | None = None
    host_key_policy: str = "reject"
    remote_atlas_root: str = "/users/user/ATLAS-1.0"
    remote_executable: str = "Runs/P_ATLAS.1.0.x"
    mpi_processes: int = 32
    launch_command_template: str = "mpirun -np {mpi_processes} {executable} {date}"
    remote_shell_preamble: str = ""
    dry_run: bool = True
    poll_seconds: int = 30
    reconnect_seconds: int = 15
    max_reconnect_attempts: int = 100
    auto_delete_unused_remote_meteo: bool = True
    cleanup_remote_simulation: bool = True
    accept_nonempty_part_on_failed_exit: bool = True
    min_remote_part_bytes: int = 1
    done_part_recheck_seconds: int = 10
    done_part_max_rechecks: int = 12
    continue_on_error: bool = False
    skip_missing_meteorology: bool = True

    def __post_init__(self):
        object.__setattr__(self, "local_inputs_root", Path(self.local_inputs_root))
        object.__setattr__(self, "local_meteorology_root", Path(self.local_meteorology_root))
        object.__setattr__(self, "local_runs_root", Path(self.local_runs_root))
        if self.private_key_path is not None:
            object.__setattr__(self, "private_key_path", Path(self.private_key_path))
        if self.phases is not None:
            object.__setattr__(self, "phases", tuple(str(x).strip() for x in self.phases))
        policy = self.host_key_policy.lower().strip()
        if policy not in {"reject", "auto_add"}:
            raise ValueError("host_key_policy must be 'reject' or 'auto_add'")
        object.__setattr__(self, "host_key_policy", policy)
        if not self.ssh_host.strip() or not self.ssh_user.strip():
            raise ValueError("ssh_host and ssh_user cannot be empty")
        if self.ssh_port <= 0 or self.mpi_processes < 1:
            raise ValueError("ssh_port and mpi_processes must be positive")
        if self.poll_seconds < 1 or self.max_reconnect_attempts < 1:
            raise ValueError("poll_seconds/max_reconnect_attempts invalid")
        if self.min_remote_part_bytes < 1:
            raise ValueError("min_remote_part_bytes must be >= 1")

    @property
    def remote_root(self):
        return PurePosixPath(self.remote_atlas_root)

    @property
    def executable(self):
        path = PurePosixPath(self.remote_executable)
        return path if path.is_absolute() else self.remote_root / path

    @property
    def password(self):
        return os.environ.get(self.password_env_var) if self.password_env_var else None


@dataclass(frozen=True)
class AtlasRemoteSimulation:
    scenario_id: str
    phase: str
    date: str
    run_folder: str
    local_input_dir: Path

    @property
    def name(self):
        return self.run_folder


class _TeeOutput:
    def __init__(self, terminal, logfile):
        self.terminal, self.logfile = terminal, logfile
    def write(self, message):
        self.terminal.write(message); self.logfile.write(message); self.logfile.flush()
    def flush(self):
        self.terminal.flush(); self.logfile.flush()
    def isatty(self):
        return getattr(self.terminal, "isatty", lambda: False)()


class AtlasRemoteRunner:
    """Resumable runner using atlas_input_manifest.csv as execution manifest."""

    def __init__(self, config: AtlasRemoteConfig):
        if paramiko is None:
            raise ImportError("Install Paramiko: python -m pip install paramiko")
        self.config = config
        self.log_file = config.local_runs_root / "atlas_remote_runs.csv"
        self.console_log_dir = config.local_runs_root / "logs"

    @staticmethod
    def timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def print_status(self, message):
        print(f"[{self.timestamp()}] {message}", flush=True)

    @property
    def manifest_path(self):
        return self.config.local_inputs_root / "atlas_input_manifest.csv"

    def discover_simulations(self):
        if not self.manifest_path.is_file():
            raise FileNotFoundError(f"Missing {self.manifest_path}; build ATLAS inputs first.")
        table = pd.read_csv(self.manifest_path, dtype={"date_key": str})
        required = {"scenario_id", "phase", "date_key", "run_folder"}
        missing = required.difference(table.columns)
        if missing:
            raise KeyError(f"Input manifest missing columns: {sorted(missing)}")
        table["date_key"] = table["date_key"].astype(str).str.zfill(8)
        if self.config.phases is not None:
            table = table.loc[table["phase"].isin(self.config.phases)]
        sims = [
            AtlasRemoteSimulation(
                scenario_id=str(row.scenario_id),
                phase=str(row.phase),
                date=str(row.date_key),
                run_folder=str(row.run_folder),
                local_input_dir=self.config.local_inputs_root / str(row.phase) / str(row.run_folder),
            )
            for row in table.itertuples(index=False)
        ]
        sims.sort(key=lambda x: (x.phase, x.date, x.run_folder))
        if not sims:
            raise AtlasRemoteError("No simulations found after phase filtering.")
        return sims

    def initialize_log(self):
        self.config.local_runs_root.mkdir(parents=True, exist_ok=True)
        if self.log_file.exists():
            return
        with self.log_file.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "timestamp","phase","simulation","date","scenario_id",
                "status","local_output","message",
            ])

    def write_log(self, sim, status, output=None, message=""):
        with self.log_file.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                self.timestamp(),sim.phase,sim.name,sim.date,sim.scenario_id,
                status,str(output) if output else "",message,
            ])

    def find_input_files(self, sim):
        main = sim.local_input_dir / f"{sim.date}.inp"
        phase = sim.local_input_dir / f"{sim.date}.Phase1.inp"
        missing = [x for x in (main, phase) if not x.is_file()]
        if missing:
            raise FileNotFoundError("Missing ATLAS inputs:\n" + "\n".join(map(str, missing)))
        return main, phase

    def find_meteorology(self, sim):
        root = self.config.local_meteorology_root / sim.phase
        expected = f"{sim.date}.era5.nc"
        matches = [p for p in root.rglob(expected) if p.is_file() and p.stat().st_size > 0] if root.exists() else []
        if not matches:
            raise FileNotFoundError(f"No non-empty {expected} below {root}")
        if len(matches) > 1:
            raise AtlasRemoteError("Multiple matching meteorologies:\n" + "\n".join(map(str,matches)))
        return matches[0]

    def local_output_dir(self, sim):
        return self.config.local_runs_root / sim.phase / sim.run_folder

    def find_existing_local_result(self, sim):
        root = self.local_output_dir(sim)
        if not root.exists():
            return None
        files = [p for p in root.rglob("*.part.nc") if p.stat().st_size >= self.config.min_remote_part_bytes]
        return max(files, key=lambda x: x.stat().st_mtime) if files else None

    def remote_runs_root(self, phase):
        return self.config.remote_root / "Runs" / phase

    def remote_meteo_root(self, phase):
        return self.config.remote_root / "Data" / "era5" / phase

    def remote_sim_dir(self, sim):
        return self.remote_runs_root(sim.phase) / sim.run_folder

    def remote_meteo(self, sim, local):
        return self.remote_meteo_root(sim.phase) / local.name

    def markers(self, sim):
        root = self.remote_sim_dir(sim)
        return {
            "dir":root, "running":root/".atlas_running", "done":root/".atlas_done",
            "failed":root/".atlas_failed", "log":root/"atlas.log",
        }

    def connect(self):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy() if self.config.host_key_policy == "auto_add"
            else paramiko.RejectPolicy()
        )
        kwargs = dict(
            hostname=self.config.ssh_host, port=self.config.ssh_port,
            username=self.config.ssh_user, timeout=30, banner_timeout=30,
            auth_timeout=30, look_for_keys=True, allow_agent=True,
        )
        if self.config.password:
            kwargs["password"] = self.config.password
        if self.config.private_key_path is not None:
            kwargs["key_filename"] = str(self.config.private_key_path)
        client.connect(**kwargs)
        transport = client.get_transport()
        if transport: transport.set_keepalive(30)
        return client

    def connect_with_retry(self):
        for attempt in range(1, self.config.max_reconnect_attempts+1):
            try:
                self.print_status(f"Connecting to {self.config.ssh_host} (attempt {attempt})")
                client = self.connect()
                self.print_status("SSH connected.")
                return client
            except Exception as exc:
                self.print_status(f"SSH connection failed: {exc}")
                if attempt == self.config.max_reconnect_attempts:
                    raise
                time.sleep(self.config.reconnect_seconds)

    @staticmethod
    def run_remote(ssh, command, check=True):
        _, stdout, stderr = ssh.exec_command(command)
        status = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if check and status != 0:
            raise AtlasRemoteError(f"Remote command failed ({status}):\n{command}\n{out}\n{err}")
        return status, out, err

    @staticmethod
    def remote_exists(sftp, path):
        try:
            sftp.stat(str(path)); return True
        except FileNotFoundError:
            return False

    def remote_mkdir_p(self, sftp, path):
        current = PurePosixPath("/") if path.is_absolute() else PurePosixPath(".")
        for part in path.parts:
            if part in {"/","."}: continue
            current = current / part
            try: sftp.stat(str(current))
            except FileNotFoundError: sftp.mkdir(str(current))

    def upload_file(self, sftp, local, remote):
        local_size = local.stat().st_size
        try:
            if sftp.stat(str(remote)).st_size == local_size:
                self.print_status(f"Upload skipped; same size: {remote}")
                return
        except FileNotFoundError:
            pass
        self.remote_mkdir_p(sftp, remote.parent)
        tmp = PurePosixPath(str(remote)+".uploading")
        try:
            try: sftp.remove(str(tmp))
            except FileNotFoundError: pass
            sftp.put(str(local), str(tmp))
            if sftp.stat(str(tmp)).st_size != local_size:
                raise IOError(f"Upload size mismatch: {local}")
            try: sftp.remove(str(remote))
            except FileNotFoundError: pass
            sftp.rename(str(tmp), str(remote))
        except Exception:
            try: sftp.remove(str(tmp))
            except Exception: pass
            raise

    def upload_directory(self, sftp, local_dir, remote_dir):
        self.remote_mkdir_p(sftp, remote_dir)
        for path in sorted(local_dir.rglob("*")):
            remote = remote_dir / path.relative_to(local_dir).as_posix()
            if path.is_dir(): self.remote_mkdir_p(sftp, remote)
            elif path.is_file(): self.upload_file(sftp, path, remote)

    def launch_command(self, sim):
        return self.config.launch_command_template.format(
            mpi_processes=self.config.mpi_processes,
            executable=shlex.quote(str(self.config.executable)),
            date=shlex.quote(sim.date),
            run_dir=shlex.quote(str(self.remote_sim_dir(sim))),
        )

    def validate_input_references(self, sim, main_input, phase_input, meteo):
        text = main_input.read_text(encoding="utf-8", errors="replace")
        expected_meteo = self.remote_meteo(sim, meteo)
        expected_phase = self.remote_sim_dir(sim) / phase_input.name
        warnings=[]
        if f"FILE        = {expected_meteo}" not in text:
            warnings.append(f"expected METEO path {expected_meteo}")
        if f"INCLUDE  = {expected_phase}" not in text:
            warnings.append(f"expected Phase1 path {expected_phase}")
        return warnings

    def validate_remote_environment(self, ssh):
        for label,path,flag in [
            ("ATLAS root",self.config.remote_root,"-d"),
            ("Runs root",self.config.remote_root/"Runs","-d"),
            ("ERA5 root",self.config.remote_root/"Data"/"era5","-d"),
            ("Executable",self.config.executable,"-x"),
        ]:
            status,_,_=self.run_remote(ssh,f"test {flag} {shlex.quote(str(path))}",check=False)
            self.print_status(f"{label}: {path} -> {'OK' if status==0 else 'NOT FOUND'}")

    def dry_run_simulation(self, ssh, sim):
        main, phase_input = self.find_input_files(sim)
        try:
            meteo=self.find_meteorology(sim)
        except FileNotFoundError as exc:
            if self.config.skip_missing_meteorology:
                self.print_status(f"SKIP {sim.phase}/{sim.name}: {exc}"); return
            raise
        self.print_status(f"Input folder: {sim.local_input_dir}")
        self.print_status(f"Meteorology: {meteo}")
        self.print_status(f"Remote run: {self.remote_sim_dir(sim)}")
        for warning in self.validate_input_references(sim,main,phase_input,meteo):
            self.print_status("WARNING: "+warning)
        self.print_status("Command: "+self.launch_command(sim))

    def find_remote_parts(self, ssh, sim):
        root=self.remote_sim_dir(sim)
        n=self.config.min_remote_part_bytes
        cmd=f"find {shlex.quote(str(root))} -type f -name '*.part.nc' -size +{n-1}c -printf '%p\\t%s\\n'"
        status,out,_=self.run_remote(ssh,cmd,check=False)
        if status!=0:return []
        found=[]
        for line in out.splitlines():
            if not line.strip(): continue
            try:
                p,s=line.rsplit("\t",1); s=int(s)
            except ValueError: continue
            if s>=n: found.append((PurePosixPath(p),s))
        return found

    def status(self, ssh, sim):
        p=self.markers(sim)
        cmd=f"""if [ -f {shlex.quote(str(p['running']))} ]; then echo RUNNING;
elif [ -f {shlex.quote(str(p['done']))} ]; then echo DONE;
elif [ -f {shlex.quote(str(p['failed']))} ]; then echo FAILED;
else echo NOT_STARTED; fi"""
        _,out,_=self.run_remote(ssh,cmd)
        marker=out.strip()
        has=bool(self.find_remote_parts(ssh,sim))
        if marker=="RUNNING": return "RUNNING"
        if marker=="DONE": return "DONE" if has else "DONE_NO_PART"
        if marker=="FAILED": return "PART_READY" if (has and self.config.accept_nonempty_part_on_failed_exit) else "FAILED"
        return "PART_READY" if has else "NOT_STARTED"

    def start(self, ssh, sim):
        p=self.markers(sim)
        pre=self.config.remote_shell_preamble.strip()
        inner=f"""cd {shlex.quote(str(p['dir']))} || exit 100
rm -f .atlas_done .atlas_failed
echo $$ > .atlas_running
{pre}
{self.launch_command(sim)}
STATUS=$?
rm -f .atlas_running
if [ "$STATUS" -eq 0 ]; then echo "$STATUS" > .atlas_done; else echo "$STATUS" > .atlas_failed; fi
exit "$STATUS"
"""
        outer="nohup bash -lc "+shlex.quote(inner)+" > "+shlex.quote(str(p["log"]))+" 2>&1 < /dev/null & echo $!"
        _,out,_=self.run_remote(ssh,outer)
        self.write_log(sim,"STARTED",message=f"Remote PID {out.strip()}")
        self.print_status(f"ATLAS started: {sim.phase}/{sim.name}, PID {out.strip()}")

    def wait_for_part_after_done(self, ssh, sim):
        for i in range(1,self.config.done_part_max_rechecks+1):
            if self.find_remote_parts(ssh,sim): return True
            self.print_status(f"DONE without part: recheck {i}/{self.config.done_part_max_rechecks}")
            time.sleep(self.config.done_part_recheck_seconds)
        return False

    def wait(self, ssh, sim):
        while True:
            try:
                state=self.status(ssh,sim)
                self.print_status(f"{sim.phase}/{sim.name}: {state}")
                if state in {"DONE","PART_READY"}: return ssh
                if state=="DONE_NO_PART":
                    if self.wait_for_part_after_done(ssh,sim): return ssh
                    raise AtlasRemoteError("DONE marker exists but no part file appeared; run left untouched.")
                if state=="FAILED":
                    p=self.markers(sim)
                    _,out,err=self.run_remote(ssh,f"tail -n 100 {shlex.quote(str(p['log']))}",check=False)
                    raise AtlasRemoteError(f"ATLAS failed without valid part file.\n{out}\n{err}")
                if state=="NOT_STARTED": self.start(ssh,sim)
                time.sleep(self.config.poll_seconds)
            except (paramiko.SSHException,socket.error,EOFError,OSError) as exc:
                self.print_status(f"SSH lost: {exc}")
                try:ssh.close()
                except Exception:pass
                time.sleep(self.config.reconnect_seconds)
                ssh=self.connect_with_retry()

    def download_result(self, ssh, sim):
        parts=self.find_remote_parts(ssh,sim)
        if len(parts)!=1:
            raise AtlasRemoteError(f"Expected exactly one valid remote part file, found {len(parts)}")
        remote,size=parts[0]
        folder=self.local_output_dir(sim); folder.mkdir(parents=True,exist_ok=True)
        local=folder/remote.name; tmp=local.with_suffix(local.suffix+".downloading")
        sftp=ssh.open_sftp()
        try:
            sftp.get(str(remote),str(tmp))
            local_size=tmp.stat().st_size
            if local_size!=size:
                tmp.unlink(missing_ok=True)
                raise IOError(f"Download size mismatch: remote={size}, local={local_size}")
            tmp.replace(local)
        finally:sftp.close()
        return local

    def pending_for(self, simulations, phase, date):
        return [s for s in simulations if s.phase==phase and s.date==date and self.find_existing_local_result(s) is None]

    def cleanup_sim(self, ssh, sim):
        if self.config.cleanup_remote_simulation:
            self.run_remote(ssh,f"rm -rf {shlex.quote(str(self.remote_sim_dir(sim)))}")

    def maybe_cleanup_meteo(self, ssh, simulations, sim):
        if not self.config.auto_delete_unused_remote_meteo:return
        if self.pending_for(simulations,sim.phase,sim.date):return
        try:local=self.find_meteorology(sim)
        except FileNotFoundError:return
        remote=self.remote_meteo(sim,local)
        self.run_remote(ssh,f"rm -f {shlex.quote(str(remote))}",check=False)

    def process_one(self, ssh, sim, simulations):
        existing=self.find_existing_local_result(sim)
        if existing:
            self.print_status(f"SKIP completed: {sim.phase}/{sim.name}")
            return ssh
        try:meteo=self.find_meteorology(sim)
        except FileNotFoundError as exc:
            if self.config.skip_missing_meteorology:
                self.write_log(sim,"SKIPPED_NO_METEO",message=str(exc))
                self.print_status(f"SKIP missing meteo: {sim.phase}/{sim.name}")
                return ssh
            raise
        main,phase_input=self.find_input_files(sim)
        warnings=self.validate_input_references(sim,main,phase_input,meteo)
        if warnings:
            raise AtlasRemoteError("Input paths do not match remote config:\n"+"\n".join(warnings))
        sftp=ssh.open_sftp()
        try:
            self.remote_mkdir_p(sftp,self.remote_runs_root(sim.phase))
            self.remote_mkdir_p(sftp,self.remote_meteo_root(sim.phase))
            self.upload_file(sftp,meteo,self.remote_meteo(sim,meteo))
            self.upload_directory(sftp,sim.local_input_dir,self.remote_sim_dir(sim))
        finally:sftp.close()
        ssh=self.wait(ssh,sim)
        result=self.download_result(ssh,sim)
        warning=self.status(ssh,sim)=="PART_READY"
        self.write_log(sim,"COMPLETED_WITH_ATLAS_WARNING" if warning else "COMPLETED",output=result)
        self.cleanup_sim(ssh,sim)
        self.maybe_cleanup_meteo(ssh,simulations,sim)
        return ssh

    def run(self):
        simulations=self.discover_simulations()
        self.print_status(f"Discovered {len(simulations)} runs; dry_run={self.config.dry_run}")
        ssh=self.connect_with_retry()
        rows=[]
        try:
            self.validate_remote_environment(ssh)
            if self.config.dry_run:
                for sim in simulations:
                    try:self.dry_run_simulation(ssh,sim); status="VALIDATED"; msg=""
                    except Exception as exc:status="VALIDATION_ERROR"; msg=str(exc)
                    rows.append({"phase":sim.phase,"simulation":sim.name,"date":sim.date,"status":status,"message":msg})
                return pd.DataFrame(rows)
            self.initialize_log()
            for sim in simulations:
                try:
                    ssh=self.process_one(ssh,sim,simulations)
                    status="COMPLETED" if self.find_existing_local_result(sim) else "SKIPPED"; msg=""
                except KeyboardInterrupt:
                    self.print_status("Interrupted locally; detached remote ATLAS may continue."); raise
                except Exception as exc:
                    status="ERROR"; msg=str(exc); self.write_log(sim,status,message=msg)
                    rows.append({"phase":sim.phase,"simulation":sim.name,"date":sim.date,"status":status,"message":msg})
                    if not self.config.continue_on_error: raise
                    continue
                rows.append({"phase":sim.phase,"simulation":sim.name,"date":sim.date,"status":status,"message":msg})
        finally:
            try:ssh.close()
            except Exception:pass
        return pd.DataFrame(rows)

    def run_with_console_log(self):
        if self.config.dry_run:return self.run()
        self.console_log_dir.mkdir(parents=True,exist_ok=True)
        path=self.console_log_dir/f"atlas_remote_{datetime.now():%Y%m%d_%H%M%S}.log"
        handle=path.open("w",encoding="utf-8",buffering=1)
        oldout,olderr=sys.stdout,sys.stderr
        sys.stdout=_TeeOutput(oldout,handle); sys.stderr=_TeeOutput(olderr,handle)
        try:
            self.print_status(f"Console log: {path}")
            return self.run()
        finally:
            sys.stdout,sys.stderr=oldout,olderr
            handle.close()


def run_atlas_remote(config: AtlasRemoteConfig) -> pd.DataFrame:
    return AtlasRemoteRunner(config).run_with_console_log()
