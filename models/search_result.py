"""
Data structure for a search result item shown in the UI.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Dict


@dataclass
class SearchResult:
    """Represents a single search result item."""
    
    id: str
    title: str
    kind: str = "general"
    subtitle: Optional[str] = None
    icon: Optional[str] = None
    path: Optional[str] = None
    command: Optional[str] = None
    action: Optional[str] = None
    source: str = "local"
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # UI-specific properties (set by controller)
    _spotlight_status: Optional[str] = None
    _spotlight_actionable: bool = False
    _spotlight_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "subtitle": self.subtitle,
            "icon": self.icon,
            "path": self.path,
            "command": self.command,
            "action": self.action,
            "source": self.source,
            **self.metadata,
            "_spotlight_status": self._spotlight_status,
            "_spotlight_actionable": self._spotlight_actionable,
            "_spotlight_action": self._spotlight_action,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """Create from dictionary representation."""
        metadata = {k: v for k, v in data.items() 
                   if k not in ("id", "title", "kind", "subtitle", "icon", 
                               "path", "command", "action", "source",
                               "_spotlight_status", "_spotlight_actionable", 
                               "_spotlight_action")}
        
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            kind=data.get("kind", "general"),
            subtitle=data.get("subtitle"),
            icon=data.get("icon"),
            path=data.get("path"),
            command=data.get("command"),
            action=data.get("action"),
            source=data.get("source", "local"),
            metadata=metadata,
            _spotlight_status=data.get("_spotlight_status"),
            _spotlight_actionable=data.get("_spotlight_actionable", False),
            _spotlight_action=data.get("_spotlight_action"),
        )
