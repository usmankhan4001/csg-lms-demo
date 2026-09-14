"""
Prometheus Metrics Engine for CSG LMS / Learnhouse API.
"""

import time
from collections import defaultdict
from typing import Dict, List


class MetricsRegistry:
    def __init__(self):
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.response_latencies: Dict[str, List[float]] = defaultdict(list)
        self.active_connections: int = 0
        self.sms_events_counter: Dict[str, int] = defaultdict(int)

    def record_request(self, method: str, path: str, status_code: int, duration_sec: float):
        key = f'{method}:{path}:{status_code}'
        self.request_counts[key] += 1
        # Keep last 50 latencies per endpoint to calculate p95
        lat_list = self.response_latencies[f'{method}:{path}']
        lat_list.append(duration_sec)
        if len(lat_list) > 50:
            lat_list.pop(0)

    def record_sms_event(self, event_type: str):
        self.sms_events_counter[event_type] += 1

    def generate_prometheus_output(self) -> str:
        lines = []
        lines.append("# HELP http_requests_total Total number of HTTP requests processed")
        lines.append("# TYPE http_requests_total counter")
        for key, count in self.request_counts.items():
            parts = key.split(":")
            if len(parts) == 3:
                m, p, s = parts
                lines.append(f'http_requests_total{{method="{m}",path="{p}",status="{s}"}} {count}')

        lines.append("# HELP http_request_duration_seconds HTTP request latency summary")
        lines.append("# TYPE http_request_duration_seconds gauge")
        for endpoint, latencies in self.response_latencies.items():
            if latencies:
                avg_lat = sum(latencies) / len(latencies)
                lines.append(f'http_request_duration_seconds{{endpoint="{endpoint}",metric="avg"}} {avg_lat:.6f}')

        lines.append("# HELP sms_business_events_total Total SMS business operations executed")
        lines.append("# TYPE sms_business_events_total counter")
        for event, count in self.sms_events_counter.items():
            lines.append(f'sms_business_events_total{{event="{event}"}} {count}')

        return "\n".join(lines) + "\n"


metrics_registry = MetricsRegistry()
