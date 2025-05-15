import os
import json
import datetime
from typing import Dict, Any, Optional, List
from django.conf import settings
from chatbot.services.rag.evaluate_rag import evaluate_and_save

HISTORY_FILE = os.path.join(settings.BASE_DIR, 'chatbot', 'data', 'test_history.json')

def run_versioned_tests(version_tag: str = None, save_history: bool = True) -> Dict[str, Any]:
    """
    Run tests and compare against previous versions to track system evolution.
    
    Args:
        version_tag: Tag for this version (defaults to date)
        save_history: Whether to save results to history file
        
    Returns:
        Dictionary with test results and comparison metrics
    """
    if not version_tag:
        # Use date as default version tag
        version_tag = datetime.datetime.now().strftime('%Y-%m-%d')
        
    # Load history of previous test runs
    history = _load_test_history()
    
    # Run current tests
    current_results = evaluate_and_save(verbose=False)
    
    # Add metadata
    test_entry = {
        "version": version_tag,
        "timestamp": datetime.datetime.now().isoformat(),
        "results": current_results
    }
    
    # Compare with previous version if available
    previous_version = _get_most_recent_version(history)
    comparison = _compare_with_previous(current_results, previous_version)
    test_entry["comparison"] = comparison
    
    # Save to history if requested
    if save_history:
        history.append(test_entry)
        _save_test_history(history)
    
    return {
        "current": test_entry,
        "previous": previous_version,
        "comparison": comparison,
        "history_count": len(history)
    }

def _load_test_history() -> List[Dict[str, Any]]:
    """Load test history from file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading test history: {str(e)}")
    return []

def _save_test_history(history: List[Dict[str, Any]]) -> None:
    """Save test history to file"""
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving test history: {str(e)}")

def _get_most_recent_version(history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Get the most recent test version from history"""
    if not history:
        return None
        
    # Sort by timestamp (newest first)
    sorted_history = sorted(
        history, 
        key=lambda x: x.get('timestamp', ''), 
        reverse=True
    )
    
    return sorted_history[0] if sorted_history else None

def _compare_with_previous(
    current: Dict[str, Any], 
    previous: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compare current test results with previous version"""
    if not previous or 'results' not in previous:
        return {"available": False}
        
    previous_results = previous['results']
    
    # Calculate differences in key metrics
    accuracy_diff = current.get('accuracy', 0) - previous_results.get('accuracy', 0)
    confidence_diff = current.get('average_confidence', 0) - previous_results.get('average_confidence', 0)
    f1_diff = current.get('macro_f1', 0) - previous_results.get('macro_f1', 0)
    
    # Identify specific cases that changed
    case_diffs = []
    
    if 'cases' in current and 'cases' in previous_results:
        curr_cases = {c['query']: c.get('correct', False) for c in current['cases']}
        prev_cases = {c['query']: c.get('correct', False) for c in previous_results['cases']}
        
        # Find cases that changed from incorrect to correct (improvements)
        for query, is_correct in curr_cases.items():
            if query in prev_cases:
                if is_correct and not prev_cases[query]:
                    case_diffs.append({
                        "query": query,
                        "change": "improved",
                    })
                elif not is_correct and prev_cases[query]:
                    case_diffs.append({
                        "query": query,
                        "change": "regressed",
                    })
    
    return {
        "available": True,
        "previous_version": previous.get('version', 'unknown'),
        "metrics_diff": {
            "accuracy": accuracy_diff,
            "confidence": confidence_diff,
            "f1_score": f1_diff,
        },
        "improved": accuracy_diff > 0,
        "case_changes": case_diffs,
        "regression_count": len([c for c in case_diffs if c['change'] == 'regressed']),
        "improvement_count": len([c for c in case_diffs if c['change'] == 'improved']),
    }

if __name__ == "__main__":
    results = run_versioned_tests()
    version = results["current"]["version"]
    
    print(f"Test results for version: {version}")
    
    if results["comparison"]["available"]:
        prev = results["comparison"]["previous_version"] 
        diff = results["comparison"]["metrics_diff"]["accuracy"] * 100
        direction = "improved" if diff > 0 else "decreased"
        
        print(f"Compared to {prev}: Accuracy {direction} by {abs(diff):.1f}%")
        print(f"Improvements: {results['comparison']['improvement_count']}")
        print(f"Regressions: {results['comparison']['regression_count']}")
    else:
        print("No previous version available for comparison")
