import datetime
from pathlib import Path

from core import reporter


REAL_DATETIME = datetime.datetime


class FixedDatetime:
    @classmethod
    def now(cls):
        return REAL_DATETIME(2026, 3, 11, 17, 30, 0)


class TestReporter:
    def test_generate_report_creates_fallback_template_and_file(self, tmp_path, monkeypatch):
        core_dir = tmp_path / "backend" / "core"
        core_dir.mkdir(parents=True)
        reporter_file = core_dir / "reporter.py"
        reporter_file.write_text("# stub", encoding="utf-8")

        monkeypatch.setattr(reporter.os.path, "abspath", lambda _: str(reporter_file))
        monkeypatch.setattr(reporter.datetime, "datetime", FixedDatetime)

        report_path = reporter.generate_report({"task_id": "task-1"}, output_dir="reports")
        report_file = Path(report_path)

        assert report_file.exists()
        assert report_file.read_text(encoding="utf-8").startswith("<html>")
        assert (tmp_path / "backend" / "templates" / "report.html").exists()

    def test_generate_report_does_not_mutate_input(self, tmp_path, monkeypatch):
        core_dir = tmp_path / "backend" / "core"
        template_dir = tmp_path / "backend" / "templates"
        reports_dir = tmp_path / "reports"
        core_dir.mkdir(parents=True)
        template_dir.mkdir(parents=True)
        reports_dir.mkdir(parents=True)
        reporter_file = core_dir / "reporter.py"
        reporter_file.write_text("# stub", encoding="utf-8")
        (template_dir / "report.html").write_text(
            "<html><body>{{ task_data.task_id }}|{{ task_data.generated_at }}</body></html>",
            encoding="utf-8",
        )

        monkeypatch.setattr(reporter.os.path, "abspath", lambda _: str(reporter_file))
        monkeypatch.setattr(reporter.datetime, "datetime", FixedDatetime)

        task_data = {"task_id": "task-2"}
        report_path = reporter.generate_report(task_data, output_dir="reports")
        content = Path(report_path).read_text(encoding="utf-8")

        assert task_data == {"task_id": "task-2"}
        assert "task-2|2026-03-11 17:30:00" in content

    def test_generate_report_returns_empty_on_failure(self, tmp_path, monkeypatch):
        core_dir = tmp_path / "backend" / "core"
        core_dir.mkdir(parents=True)
        reporter_file = core_dir / "reporter.py"
        reporter_file.write_text("# stub", encoding="utf-8")

        monkeypatch.setattr(reporter.os.path, "abspath", lambda _: str(reporter_file))

        def raise_os_error(*args, **kwargs):
            raise OSError("cannot write")

        monkeypatch.setattr(reporter.os, "makedirs", raise_os_error)

        assert reporter.generate_report({"task_id": "task-3"}, output_dir="reports") == ""
