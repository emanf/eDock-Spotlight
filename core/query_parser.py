"""
Query parser for determining search mode and query parameters.
"""
from .constants import QUERY_MODE_NORMAL, QUERY_MODE_APPS


class QueryParser:
    """Parses user input and determines query mode."""
    
    @staticmethod
    def parse(query: str) -> tuple[str, str]:
        """
        Parse a query string and return (mode, cleaned_query).
        
        Args:
            query: Raw user input
            
        Returns:
            Tuple of (mode, cleaned_query) where mode is QUERY_MODE_NORMAL or QUERY_MODE_APPS
        """
        query = str(query or "").strip()
        
        if query.startswith(">"):
            # Apps discovery mode
            cleaned = query[1:].strip()
            return QUERY_MODE_APPS, cleaned
        
        # Normal search mode
        return QUERY_MODE_NORMAL, query
    
    @staticmethod
    def get_mode(query: str) -> str:
        """Get just the mode for a query."""
        mode, _ = QueryParser.parse(query)
        return mode
    
    @staticmethod
    def get_query(query: str) -> str:
        """Get just the cleaned query."""
        _, cleaned = QueryParser.parse(query)
        return cleaned
