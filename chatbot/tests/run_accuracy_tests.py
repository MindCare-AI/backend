from chatbot.services.rag.evaluate_rag import evaluate_and_save

def run_tests(save: bool = False) -> dict:
    """
    Run RAG evaluation and adapt results for the test_chatbot_accuracy command.
    """
    # Save to JSON if requested
    out_file = "chatbot_accuracy_results.json" if save else None
    results = evaluate_and_save(output_file=out_file, verbose=False)

    metrics = {
        "approach_accuracy": results.get("accuracy", 0),
        "avg_keyword_score": results.get("average_confidence", 0),
        "comprehensive_score": results.get("macro_f1", 0),
    }

    ret = {
        "metrics": metrics,
        "success": metrics["approach_accuracy"] >= 0.7,
    }
    if save:
        ret["results_file"] = out_file
    return ret
