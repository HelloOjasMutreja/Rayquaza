def handle_chat(payload: dict, router, meter) -> dict:
    """Pure handler: Ollama-style chat payload -> Ollama-style response dict.

    Routes to a provider, meters usage, and normalizes both success and failure to
    shapes the engine already understands (it reads response['message']['content']).
    """
    model = payload.get("model", "")
    messages = payload.get("messages", [])
    fmt = payload.get("format")
    if meter.over_budget():
        return {"model": model, "error": "budget cap reached, refusing further API calls",
                "done": True, "message": {"role": "assistant", "content": ""}}
    try:
        provider = router.provider_for(model)
        result = provider.chat(model, messages, fmt)
        meter.record(result.usage)
        return {"model": model, "message": {"role": "assistant", "content": result.text},
                "done": True}
    except Exception as exc:  # provider/network/key failure -> ollama-shaped error
        return {"model": model, "error": str(exc), "done": True,
                "message": {"role": "assistant", "content": ""}}
