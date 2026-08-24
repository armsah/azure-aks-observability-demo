import os
import time
from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

try:
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
except ImportError:
    AzureMonitorTraceExporter = None

app = Flask(__name__)
metrics = PrometheusMetrics(app, defaults_prefix="monitoring_demo")

resource = Resource.create({
    "service.name": "azure-monitoring-demo",
    "service.version": os.getenv("APP_VERSION", "dev"),
    "deployment.environment": os.getenv("ENVIRONMENT", "local"),
})

trace_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

if connection_string and AzureMonitorTraceExporter:
    exporter = AzureMonitorTraceExporter(connection_string=connection_string)
    trace_provider.add_span_processor(BatchSpanProcessor(exporter))

FlaskInstrumentor().instrument_app(app)


@app.get("/")
def index():
    return jsonify({
        "message": "Hello from Azure!",
        "service": "azure-monitoring-demo",
        "version": os.getenv("APP_VERSION", "dev"),
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/slow")
def slow():
    delay = float(os.getenv("SLOW_ENDPOINT_DELAY_SECONDS", "2"))
    with tracer.start_as_current_span("intentional-slow-operation") as span:
        span.set_attribute("demo.intentional_delay_seconds", delay)
        time.sleep(delay)
    return jsonify({"status": "slow", "delay_seconds": delay})


@app.get("/error")
def error():
    with tracer.start_as_current_span("intentional-error") as span:
        span.record_exception(RuntimeError("Intentional demo failure"))
        span.set_status(trace.Status(trace.StatusCode.ERROR))
    return jsonify({"error": "intentional demo error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
