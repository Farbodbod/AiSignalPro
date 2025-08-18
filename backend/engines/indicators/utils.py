# backend/engines/indicators/utils.py
import json
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    """
    Creates a unique, stable, and hashable key from an indicator's parameters.
    This is the central utility function used by the analyzer and indicators
    to ensure consistent key generation across the system.
    """
    try:
        filtered_params = {
            k: v
            for k, v in params.items()
            if k not in ["enabled", "dependencies", "name"]
        }
        if not filtered_params:
            return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(",", ":"))
        return f"{name}_{param_str}"
    except TypeError as e:
        logger.error(f"Could not serialize params for {name}: {e}")
        param_str = "_".join(
            f"{k}_{v}"
            for k, v in sorted(params.items())
            if k not in ["enabled", "dependencies", "name"]
        )
        return f"{name}_{param_str}" if param_str else name
