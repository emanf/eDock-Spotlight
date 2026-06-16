"""Central search controller."""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..models import SearchResult
from ..core.constants import (
    QUERY_MODE_APPS, QUERY_MODE_NORMAL, KIND_LOCAL, DEFAULT_MAX_RESULTS
)
from ..core.query_parser import QueryParser
from ..core.result_merger import ResultMerger
from ..providers import LocalAppsProvider, RegistryProvider
from ..services import RegistryService, CacheService


class Controller:
    """Central coordinator for search operations."""
    
    def __init__(self, app_ref=None):
        """
        Initialize the controller.
        
        Args:
            app_ref: Reference to the app object
        """
        self.app_ref = app_ref
        self.window = None
        self.search_callback = None
        
        # Initialize services
        self.cache_service = CacheService()
        self.registry_service = RegistryService(self.cache_service)
        
        # Initialize providers
        self.local_apps_provider = LocalAppsProvider()
        
        # Configuration
        self.config = self._load_config()
    
    def set_window(self, window):
        """Set the window reference."""
        self.window = window
    
    def set_search_callback(self, callback):
        """Set callback for search results."""
        self.search_callback = callback
    
    def search(self, query: str, mode: str = QUERY_MODE_NORMAL) -> List[SearchResult]:
        """
        Execute a search.
        
        Args:
            query: Search query
            mode: Search mode (normal or apps)
            
        Returns:
            List of SearchResult objects
        """
        if not query:
            results = []
        elif mode == QUERY_MODE_APPS:
            # Apps discovery mode: search both local and registry
            results = self._search_apps_mode(query)
        else:
            # Normal mode: only search local
            results = self.local_apps_provider.search(query)
        
        # Decorate results with UI-specific properties
        decorated_results = [self._decorate_result(result, mode) for result in results]
        
        # Update window if set
        if self.window:
            self.window.update_results(decorated_results)
        
        # Call search callback if set
        if self.search_callback:
            self.search_callback(decorated_results)
        
        return decorated_results
    
    def _search_apps_mode(self, query: str) -> List[SearchResult]:
        """Search both local apps and registry in > mode."""
        results_by_provider = {}
        
        # Get installed app IDs for the registry provider
        installed_ids = self._get_installed_app_ids()
        
        # Search local apps
        local_results = self.local_apps_provider.search(query)
        results_by_provider["local"] = local_results
        
        # Search registry
        registry_provider = RegistryProvider(self.registry_service, installed_ids)
        registry_results = registry_provider.search(query)
        results_by_provider["registry"] = registry_results
        
        # Merge and deduplicate by ID
        merged = self._merge_apps_results(local_results, registry_results)
        
        return merged
    
    def _merge_apps_results(self, local_results: List[SearchResult], registry_results: List[SearchResult]) -> List[SearchResult]:
        """
        Merge local and registry results in > mode.
        
        Rules:
        - Local apps take precedence (already installed)
        - Registry results without local counterpart are added
        - Deduplicate by ID
        """
        merged = {}
        
        # Add local apps first (higher priority)
        for result in local_results:
            app_id = result.id.lower()
            merged[app_id] = result
        
        # Add registry results (only if not already present)
        for result in registry_results:
            app_id = result.id.lower()
            if app_id not in merged:
                merged[app_id] = result
        
        # Sort by title
        sorted_results = sorted(
            merged.values(),
            key=lambda r: r.title.lower()
        )
        
        return sorted_results[:DEFAULT_MAX_RESULTS]
    
    def handle_result_action(self, result_dict: Dict):
        """
        Handle an action on a result (click/enter).
        
        Args:
            result_dict: Dictionary containing result data
        """
        kind = str(result_dict.get("kind", "")).lower().strip()
        
        # Local app action
        if kind == KIND_LOCAL:
            self._show_app_info(result_dict)
        
        # Online app action
        elif result_dict.get("is_online"):
            self._show_app_info(result_dict)
        
        # Executable/shortcut - launch it
        elif kind in ("executable", "shortcut"):
            self._launch_item(result_dict)
    
    def _show_app_info(self, app_data: Dict):
        """Show app information dialog."""
        from ..ui.dialogs import AppInfoDialog
        
        if not self.window:
            return
        
        dialog = AppInfoDialog(app_data, self.window)
        if dialog.exec():
            # User clicked install - would handle installation here
            print(f"Installing app: {app_data.get('id')}")
    
    def _launch_item(self, item_data: Dict):
        """Launch an executable or shortcut."""
        import subprocess
        
        command = item_data.get("command") or item_data.get("path")
        if command:
            try:
                subprocess.Popen(command, shell=True)
            except Exception as e:
                print(f"Error launching {command}: {e}")
    
    def _get_installed_app_ids(self) -> set:
        """Get set of installed app IDs."""
        installed = set()
        
        try:
            apps_dir = self.local_apps_provider.apps_dir
            if apps_dir and apps_dir.exists():
                for app_dir in apps_dir.iterdir():
                    if app_dir.is_dir():
                        installed.add(app_dir.name.lower())
        except Exception:
            pass
        
        return installed
    
    def _decorate_result(self, result: SearchResult, mode: str) -> SearchResult:
        """
        Decorate a result with UI-specific properties.
        
        Args:
            result: SearchResult to decorate
            mode: Current search mode
            
        Returns:
            Decorated SearchResult (as dict)
        """
        decorated = result.to_dict()
        kind = str(result.kind or "").lower().strip()
        
        # Determine status and actionability based on mode and type
        if mode == QUERY_MODE_APPS:
            # In > mode: show install status for online apps
            if kind == KIND_LOCAL:
                decorated["_spotlight_status"] = "installed"
                decorated["_spotlight_actionable"] = True
                decorated["_spotlight_action"] = "showcase"
            elif result.metadata.get("is_online"):
                installed = result.metadata.get("installed", False)
                decorated["_spotlight_status"] = "installed" if installed else "install"
                decorated["_spotlight_actionable"] = not installed
                decorated["_spotlight_action"] = "install"
        else:
            # Normal mode
            if kind == KIND_LOCAL:
                decorated["_spotlight_status"] = ""
                decorated["_spotlight_actionable"] = False
            elif kind in ("executable", "shortcut"):
                decorated["_spotlight_status"] = "win"
                decorated["_spotlight_actionable"] = False
        
        return decorated
    
    def _load_config(self) -> Dict:
        """Load user configuration."""
        config_file = self._get_config_file()
        
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return {}
    
    def _save_config(self, config: Dict):
        """Save user configuration."""
        config_file = self._get_config_file()
        
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.config = config
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _get_config_file(self) -> Path:
        """Get the config file path."""
        try:
            from core.paths import get_app_data_dir
            return Path(get_app_data_dir("emanf.spotlight")) / "config.json"
        except Exception:
            home = Path.home()
            return home / ".edock" / "apps" / "emanf.spotlight" / "config.json"

