import logging
import os
import datetime
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

def generate_report(task_data: Dict[str, Any], output_dir: str = "reports") -> str:
    """
    Generate a single-file HTML report from task data.
    """
    try:
        # Resolve paths
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(base_dir, "templates")

        # Ensure output dir exists
        full_output_dir = os.path.join(os.path.dirname(base_dir), output_dir)
        os.makedirs(full_output_dir, exist_ok=True)

        # Setup Jinja2
        # Note: If template dir doesn't exist, we might need a fallback or create it.
        # Ideally we assume it exists or use embedded string template.
        if not os.path.exists(template_dir):
            os.makedirs(template_dir, exist_ok=True)
            # Create dummy template if missing
            with open(os.path.join(template_dir, "report.html"), "w", encoding="utf-8") as f:
                f.write("<html><body><h1>Test Report</h1><pre>{{ task_data | tojson(indent=2) }}</pre></body></html>")

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("report.html")

        # Avoid modifying caller-provided data
        render_data = dict(task_data)
        render_data.setdefault("generated_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Render
        html_content = template.render(task_data=render_data)

        # Save
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.html"
        file_path = os.path.join(full_output_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Report generated: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return ""
