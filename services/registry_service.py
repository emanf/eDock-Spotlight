"""Registry service for managing app packages."""
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import List, Dict, Any

from ..core.constants import APP_ID, DEFAULT_INDEXES_FILE, USER_INDEXES_FILE


class RegistryService:
    """Service for managing and fetching application registry."""
    
    def __init__(self, cache_service=None):
        """
        Initialize the registry service.
        
        Args:
            cache_service: Optional cache service for storing registry data
        """
        self.cache_service = cache_service
        self._packages_cache = None
        self._index_urls_cache = None
    
    def get_packages(self) -> List[Dict[str, Any]]:
        """
        Get all packages from the registry.
        
        Returns:
            List of package dictionaries
        """
        if self._packages_cache is not None:
            return self._packages_cache
        
        packages = []
        for source in self._get_index_urls():
            try:
                source_packages = self._read_packages_index(source)
                packages.extend(source_packages)
            except Exception as e:
                print(f"Error reading packages from {source}: {e}")
        
        self._packages_cache = packages
        return packages
    
    def clear_cache(self):
        """Clear the cached packages."""
        self._packages_cache = None
        self._index_urls_cache = None
    
    def _get_index_urls(self) -> List[str]:
        """
        Get the list of registry index URLs.
        
        Returns:
            List of URLs to fetch package indices from
        """
        if self._index_urls_cache is not None:
            return self._index_urls_cache
        
        # Try to read from user config
        indexes_path = self._ensure_user_indexes_file()
        if not indexes_path or not os.path.exists(indexes_path):
            return []
        
        try:
            with open(indexes_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []
        
        urls = []
        
        if isinstance(data, dict):
            # Try different keys
            urls = data.get("app_indexes") or data.get("indexes") or data.get("urls") or []
        elif isinstance(data, list):
            urls = data
        
        # Deduplicate while preserving order
        result = []
        seen = set()
        for url in urls:
            url_str = str(url or "").strip()
            if url_str and url_str not in seen:
                result.append(url_str)
                seen.add(url_str)
        
        self._index_urls_cache = result
        return result
    
    def _ensure_user_indexes_file(self) -> Path:
        """
        Ensure the user indexes file exists.
        
        Returns:
            Path to the user indexes file
        """
        app_data_dir = self._get_app_data_dir()
        if not app_data_dir:
            return None
        
        os.makedirs(app_data_dir, exist_ok=True)
        user_indexes_path = app_data_dir / USER_INDEXES_FILE
        
        if user_indexes_path.exists():
            return user_indexes_path
        
        # Try to copy from default
        default_indexes_path = self._get_default_indexes_path()
        try:
            if default_indexes_path and default_indexes_path.exists():
                import shutil
                shutil.copyfile(str(default_indexes_path), str(user_indexes_path))
            else:
                # Create empty indexes file
                with open(user_indexes_path, "w", encoding="utf-8") as f:
                    json.dump({"app_indexes": []}, f, indent=2)
        except Exception as e:
            print(f"Error creating user indexes file: {e}")
            if default_indexes_path and default_indexes_path.exists():
                return default_indexes_path
            return None
        
        return user_indexes_path
    
    def _get_app_data_dir(self) -> Path:
        """
        Get the application data directory.
        
        Returns:
            Path to app data directory
        """
        try:
            from core.paths import get_app_data_dir
            return Path(get_app_data_dir(APP_ID))
        except Exception:
            pass
        
        home = Path.home()
        return home / ".edock" / "apps" / APP_ID
    
    def _get_default_indexes_path(self) -> Path:
        """
        Get the path to the default indexes file.
        
        Returns:
            Path to default_indexes.json
        """
        app_dir = Path(__file__).resolve().parent.parent
        return app_dir / DEFAULT_INDEXES_FILE
    
    def _read_packages_index(self, source: str) -> List[Dict[str, Any]]:
        """
        Read packages from a single registry source.
        
        Args:
            source: URL or file path to the registry
            
        Returns:
            List of package dictionaries
        """
        source = str(source or "").strip()
        if not source:
            return []
        
        try:
            text = self._read_text_source(source)
            if not text:
                return []
            
            data = json.loads(text)
        except Exception as e:
            print(f"Error reading packages index from {source}: {e}")
            return []
        
        # Try to extract packages from various possible structures
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        
        if not isinstance(data, dict):
            return []
        
        # Try common keys for package arrays
        for key in ("packages", "apps", "items", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        
        # Single package format
        if any(key in data for key in ("id", "title", "name", "manifest", "manifest_url", "download")):
            return [data]
        
        return []
    
    def _read_text_source(self, source: str) -> str:
        """
        Read text from a source (URL or file).
        
        Args:
            source: URL or file path
            
        Returns:
            Text content
        """
        if source.startswith(("http://", "https://")):
            # Download from URL
            request = urllib.request.Request(
                source,
                headers={
                    "User-Agent": "eDock-Spotlight/1.0",
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                return response.read().decode("utf-8", errors="replace")
        
        # Read from file
        path = Path(source).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
