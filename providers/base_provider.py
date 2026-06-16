"""Base provider interface for search providers."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ..models import SearchResult


class BaseProvider(ABC):
    """Abstract base class for search providers."""
    
    @abstractmethod
    def search(self, query: str) -> List[SearchResult]:
        """
        Search for results matching the query.
        
        Args:
            query: Search query string
            
        Returns:
            List of SearchResult objects
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the provider name for logging/debugging."""
        pass
