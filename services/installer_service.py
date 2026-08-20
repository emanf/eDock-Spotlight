import shutil
import urllib.request
from pathlib import Path
from typing import Callable, Optional
import hashlib
import zipfile
import json
from packaging.version import Version, InvalidVersion


class InstallerService:
    def __init__(self, apps_dir: Path = None, cache_dir: Path = None):
        self.apps_dir = apps_dir
        self.cache_dir = cache_dir
        self.last_message = ""
        self.last_action = "install"

        if self.apps_dir is None:
            self._discover_apps_dir()
        if self.cache_dir is None:
            self._discover_cache_dir()

    def _discover_apps_dir(self):
        try:
            from core.paths import get_apps_dir

            self.apps_dir = Path(get_apps_dir())
        except Exception:
            current = Path(__file__).resolve()
            for parent in current.parents:
                apps_candidate = parent / "apps"
                if apps_candidate.exists():
                    self.apps_dir = apps_candidate
                    return
            self.apps_dir = Path.cwd() / "apps"

    def _discover_cache_dir(self):
        try:
            from core.paths import get_app_data_dir

            self.cache_dir = Path(get_app_data_dir("emanf.spotlight"))
        except Exception:
            home = Path.home()
            self.cache_dir = home / ".edock" / "cache"

    def install(
        self,
        app_id: str,
        download_url: str,
        expected_sha256: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        self.last_message = ""
        self.last_action = "install"
        if not download_url:
            self.last_message = "No download URL provided."
            print("No download URL provided")
            return False
        app_id = str(app_id or "").strip()
        if not app_id or app_id in {".", ".."} or "/" in app_id or "\\" in app_id:
            self.last_message = "Invalid app id."
            print("Invalid app id")
            return False

        temp_dir = self.cache_dir / "downloads" / app_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        zip_path = temp_dir / f"{app_id}.zip"

        try:
            self._download_file(download_url, zip_path, progress_callback)

            if expected_sha256:
                actual_hash = self._calculate_sha256(zip_path)
                if actual_hash.lower() != expected_sha256.lower():
                    self.last_message = "The downloaded archive failed checksum validation."
                    print(
                        f"Hash mismatch: expected {expected_sha256}, got {actual_hash}"
                    )
                    return False

            app_target = self.apps_dir / app_id
            self._extract_zip(zip_path, app_target)

            if not self.last_message:
                self.last_message = f"{app_id} installed successfully."
            return True
        except Exception as e:
            self.last_message = str(e)
            print(f"Error installing {app_id}: {e}")
            return False

    def _download_file(
        self, url: str, dest: Path, progress_callback: Optional[Callable] = None
    ):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "eDock-Spotlight/1.0",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

    def _calculate_sha256(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def _extract_zip(self, zip_path: Path, target_dir: Path):
        staging_dir = target_dir.parent / f".{target_dir.name}.installing"
        if staging_dir.exists():
            shutil.rmtree(str(staging_dir))
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                names = []
                for member in zip_ref.infolist():
                    name = str(member.filename).replace("\\", "/").strip("/")
                    if name.startswith("../") or "/../" in name:
                        raise ValueError("Archive contains an unsafe path")
                    if not member.is_dir() and name:
                        names.append(name)

                root_files = {name for name in names if "/" not in name}
                top_dirs = {name.split("/", 1)[0] for name in names if "/" in name}
                nested_id_prefix = f"{target_dir.name}/"
                nested_files = {
                    name[len(nested_id_prefix) :]
                    for name in names
                    if name.startswith(nested_id_prefix)
                }

                if {"app.py", "app.json"}.issubset(root_files):
                    source_prefix = ""
                elif (
                    len(top_dirs) == 1
                    and target_dir.name.casefold() in {d.casefold() for d in top_dirs}
                    and {"app.py", "app.json"}.issubset(nested_files)
                ):
                    source_prefix = nested_id_prefix
                else:
                    raise ValueError(
                        "Archive must contain app.py and app.json at its root "
                        "or inside one folder named after the app id."
                    )

                manifest_name = f"{source_prefix}app.json"
                try:
                    manifest_data = json.loads(
                        zip_ref.read(manifest_name).decode("utf-8")
                    )
                except Exception as exc:
                    raise ValueError(f"Invalid app.json in archive: {exc}") from exc

                manifest_id = str((manifest_data or {}).get("id") or "").strip()
                if manifest_id.casefold() != target_dir.name.casefold():
                    raise ValueError(
                        f"Archive app.json id '{manifest_id or '(missing)'}' "
                        f"does not match '{target_dir.name}'."
                    )

                payload = staging_dir / "payload"
                payload.mkdir(parents=True, exist_ok=True)
                payload_root = payload.resolve()
                for member in zip_ref.infolist():
                    name = str(member.filename).replace("\\", "/").strip("/")
                    if member.is_dir() or not name.startswith(source_prefix):
                        continue
                    relative = name[len(source_prefix) :]
                    if not relative:
                        continue
                    destination = (payload / relative).resolve()
                    if payload_root not in destination.parents:
                        raise ValueError("Archive contains an unsafe path")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with zip_ref.open(member, "r") as source, open(destination, "wb") as out:
                        shutil.copyfileobj(source, out)

            if not (payload / "app.py").exists() or not (payload / "app.json").exists():
                raise ValueError("The extracted app is missing app.py or app.json.")

            existing_manifest = target_dir / "app.json"
            if target_dir.exists():
                if not existing_manifest.exists():
                    raise ValueError(
                        f"An existing app folder '{target_dir.name}' contains "
                        "different data and cannot be replaced automatically."
                    )
                try:
                    existing_data = json.loads(
                        existing_manifest.read_text(encoding="utf-8")
                    )
                except Exception as exc:
                    raise ValueError(
                        f"An existing app folder '{target_dir.name}' has invalid app.json."
                    ) from exc
                existing_id = str((existing_data or {}).get("id") or "").strip()
                if existing_id.casefold() != target_dir.name.casefold():
                    raise ValueError(
                        f"Another app with different data already uses '{target_dir.name}'."
                    )
                old_version = str((existing_data or {}).get("version") or "").strip()
                new_version = str((manifest_data or {}).get("version") or "").strip()
                self.last_action = self._version_action(old_version, new_version)
                self.last_message = (
                    f"{target_dir.name} {self.last_action} successfully "
                    f"({old_version or 'unknown'} → {new_version or 'unknown'})."
                )

            replacement = target_dir.parent / f".{target_dir.name}.replacement"
            if replacement.exists():
                shutil.rmtree(str(replacement))
            shutil.move(str(payload), str(replacement))

            backup = target_dir.parent / f".{target_dir.name}.backup"
            if backup.exists():
                shutil.rmtree(str(backup))
            if target_dir.exists():
                target_dir.rename(backup)
            try:
                replacement.rename(target_dir)
            except Exception:
                if backup.exists() and not target_dir.exists():
                    backup.rename(target_dir)
                raise
            if backup.exists():
                shutil.rmtree(str(backup), ignore_errors=True)
        finally:
            if staging_dir.exists():
                shutil.rmtree(str(staging_dir), ignore_errors=True)

    @staticmethod
    def _version_action(old_version: str, new_version: str) -> str:
        if not old_version or not new_version:
            return "updated"
        try:
            old = Version(old_version)
            new = Version(new_version)
        except InvalidVersion:
            return "updated"
        if new > old:
            return "updated"
        if new < old:
            return "downgraded"
        return "reinstalled"
