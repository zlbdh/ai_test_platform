import json
from pathlib import Path
from unittest.mock import patch

from services.deploy_models import cmd_available, detect_tech_stack, dir_name_from_url


def test_cmd_available_uses_shutil_which():
    with patch("services.deploy_models.shutil.which", return_value="C:\\tools\\git.exe"):
        assert cmd_available("git") is True

    with patch("services.deploy_models.shutil.which", return_value=None):
        assert cmd_available("git") is False


def test_dir_name_from_url_strips_git_suffix_and_trailing_slash():
    assert dir_name_from_url("https://example.com/demo.git") == "demo"
    assert dir_name_from_url("https://example.com/demo/") == "demo"


def test_detect_tech_stack_for_react_vite_project(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({
            "scripts": {"dev": "vite"},
            "dependencies": {"react": "^19.0.0"},
            "devDependencies": {"vite": "^7.0.0"},
        }),
        encoding="utf-8",
    )

    result = detect_tech_stack(tmp_path)

    assert "React" in result["tech_stack"]
    assert "Vite" in result["tech_stack"]
    assert result["install_cmd"] == "npm install"
    assert result["start_cmd"] == "npm run dev"
    assert result["port"] == 3000


def test_detect_tech_stack_for_maven_wrapper_project(tmp_path: Path):
    (tmp_path / "pom.xml").write_text(
        """
<project>
  <properties>
    <java.version>17</java.version>
  </properties>
  <dependencies>
    <dependency>spring-cloud</dependency>
  </dependencies>
</project>
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "mvnw.cmd").write_text("", encoding="utf-8")

    result = detect_tech_stack(tmp_path)

    assert result["tech_stack"] == "Java 17 + Spring Cloud"
    assert result["install_cmd"] == ".\\mvnw.cmd clean install -DskipTests"
    assert result["start_cmd"] == ".\\mvnw.cmd spring-boot:run"
    assert result["port"] == 8080


def test_detect_tech_stack_for_django_project(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("Django==5.2.0\n", encoding="utf-8")
    (tmp_path / "manage.py").write_text("print('django')\n", encoding="utf-8")

    result = detect_tech_stack(tmp_path)

    assert result["tech_stack"] == "Python + Django"
    assert result["install_cmd"] == "pip install -r requirements.txt"
    assert result["start_cmd"] == "python manage.py runserver"
    assert result["port"] == 8000
