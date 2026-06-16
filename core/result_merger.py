"""Result merger for combining results from multiple providers."""
from typing import List, Dict, Set
from ..models import SearchResult
from ..core.constants import KIND_LOCAL, PRIORITY_LOCAL, PRIORITY_SHORTCUT, PRIORITY_EXECUTABLE, PRIORITY_GENERAL


class ResultMerger:
    """Merges and deduplicates results from multiple providers."""
    
    @staticmethod
    def merge(
        results_by_provider: Dict[str, List[SearchResult]],
        max_results: int = 30
    ) -> List[SearchResult]:
        """
        Merge results from multiple providers.
        
        Rules:
        - Remove duplicates (same ID/path)
        - Keep highest priority version if duplicates
        - Sort by source priority and relevance
        - Limit to max_results
        
        Args:
            results_by_provider: Dict of provider_name -> list of results
            max_results: Maximum number of results to return
            
        Returns:
            Merged and sorted list of results
        """
        if not results_by_provider:
            return []
        
        # Merge all results
        seen: Dict[str, tuple[SearchResult, int]] = {}  # canonical_key -> (result, score)
        
        for provider_name, results in results_by_provider.items():
            for result in results:
                key = ResultMerger._canonical_key(result)
                score = ResultMerger._score_result(result, provider_name)
                
                if key not in seen:
                    seen[key] = (result, score)
                else:
                    # Keep the higher priority version
                    existing_result, existing_score = seen[key]
                    if score > existing_score:
                        seen[key] = (result, score)
                    elif score == existing_score:
                        # Same score, prefer based on kind priority
                        existing_priority = ResultMerger._get_kind_priority(existing_result.kind)
                        new_priority = ResultMerger._get_kind_priority(result.kind)
                        if new_priority > existing_priority:
                            seen[key] = (result, score)
        
        # Sort by score and return
        sorted_results = sorted(
            seen.values(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [result for result, _ in sorted_results[:max_results]]
    
    @staticmethod
    def _canonical_key(result: SearchResult) -> str:
        """Get canonical key for deduplication."""
        if result.kind == KIND_LOCAL and result.id:
            return f"local:{result.id.lower()}"
        
        if result.path:
            from pathlib import Path
            stem = Path(result.path).stem.lower()
            
            # Common Windows system tools
            if stem in ("notepad", "calc", "mspaint", "cmd", "powershell", 
                       "explorer", "regedit", "taskmgr", "control"):
                return f"system:{stem}"
            
            return f"pathstem:{stem}"
        
        if result.id:
            return f"id:{result.id.lower()}"
        
        return f"title:{result.title.lower()}"
    
    @staticmethod
    def _score_result(result: SearchResult, provider_name: str) -> int:
        """Score a result based on its source."""
        # Base score from kind priority
        kind_priority = ResultMerger._get_kind_priority(result.kind)
        base_score = kind_priority * 100
        
        return base_score
    
    @staticmethod
    def _get_kind_priority(kind: str) -> int:
        """Get priority for a result kind."""
        kind_lower = str(kind or "").lower().strip()
        
        if kind_lower == KIND_LOCAL:
            return PRIORITY_LOCAL
        elif kind_lower == "shortcut":
            return PRIORITY_SHORTCUT
        elif kind_lower == "executable":
            return PRIORITY_EXECUTABLE
        
        return PRIORITY_GENERAL
