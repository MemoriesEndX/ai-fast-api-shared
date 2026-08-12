import time
import threading
from typing import Dict, Any, List, Optional


class MetricsRegistry:
    """Lightweight, thread-safe in-memory Metrics Registry for Production Observability."""

    def __init__(self):
        self._lock = threading.Lock()
        # Counters: metric_key -> float value
        self._counters: Dict[str, float] = {}
        # Histograms / Durations: metric_key -> List of float values
        self._histograms: Dict[str, List[float]] = {}
        # Metric metadata: metric_name -> help text
        self._help: Dict[str, str] = {
            "ai_requests_total": "Total count of AI chat requests processed",
            "ai_request_errors_total": "Total count of AI request error responses",
            "ai_request_latency_seconds": "AI request total latency duration in seconds",
            "llm_requests_total": "Total count of LLM inference calls",
            "llm_latency_seconds": "LLM inference execution latency in seconds",
            "llm_tokens_total": "Total tokens consumed by LLM inference",
            "qdrant_requests_total": "Total count of Qdrant vector operations",
            "qdrant_latency_seconds": "Qdrant vector query and ingestion latency in seconds",
            "mcp_tool_calls_total": "Total count of MCP tool executions",
            "mcp_tool_latency_seconds": "MCP tool execution latency in seconds",
            "rag_requests_total": "Total count of RAG retrieval executions",
            "rag_latency_seconds": "RAG vector retrieval latency in seconds",
            "recommendation_requests_total": "Total count of recommendation calculations",
            "recommendation_latency_seconds": "Recommendation engine latency in seconds",
        }

    def _format_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if not labels:
            return name
        # Sort labels to ensure consistent key hashing
        sorted_labels = ",".join([f'{k}="{v}"' for k, v in sorted(labels.items())])
        return f"{name}{{{sorted_labels}}}"

    def inc(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a metric counter."""
        key = self._format_key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record an observation (latency / duration) in seconds."""
        key = self._format_key(name, labels)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            # Bound histogram sample size to avoid unbounded memory usage
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]

    def generate_prometheus_metrics(self) -> str:
        """Export metrics in standard Prometheus text exposition format."""
        lines = []
        with self._lock:
            # Group keys by metric name
            metric_keys: Dict[str, List[str]] = {}
            for key in set(list(self._counters.keys()) + list(self._histograms.keys())):
                base_name = key.split("{")[0]
                metric_keys.setdefault(base_name, []).append(key)

            for base_name, keys in sorted(metric_keys.items()):
                help_str = self._help.get(base_name, f"{base_name} metric")
                lines.append(f"# HELP {base_name} {help_str}")
                lines.append(f"# TYPE {base_name} {'gauge' if 'latency' in base_name else 'counter'}")

                for k in sorted(keys):
                    if k in self._counters:
                        lines.append(f"{k} {self._counters[k]}")
                    if k in self._histograms and self._histograms[k]:
                        vals = self._histograms[k]
                        count = len(vals)
                        total_sum = sum(vals)
                        avg = total_sum / count if count > 0 else 0.0
                        # Output count and sum for histogram
                        sum_key = k.replace(base_name, f"{base_name}_sum")
                        count_key = k.replace(base_name, f"{base_name}_count")
                        lines.append(f"{sum_key} {total_sum:.4f}")
                        lines.append(f"{count_key} {count}")
                        lines.append(f"{k} {avg:.4f}")
        return "\n".join(lines) + "\n"

    def generate_json_metrics(self) -> Dict[str, Any]:
        """Export metrics snapshot in structured JSON format."""
        result: Dict[str, Any] = {
            "timestamp": time.time(),
            "counters": {},
            "histograms": {},
        }
        with self._lock:
            for k, v in self._counters.items():
                result["counters"][k] = v
            for k, vals in self._histograms.items():
                if vals:
                    result["histograms"][k] = {
                        "count": len(vals),
                        "sum": round(sum(vals), 4),
                        "avg": round(sum(vals) / len(vals), 4),
                        "min": round(min(vals), 4),
                        "max": round(max(vals), 4),
                    }
        return result


# Singleton Metrics Instance
metrics_registry = MetricsRegistry()
