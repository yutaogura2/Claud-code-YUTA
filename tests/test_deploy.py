from pathlib import Path

import yaml
from flask import Flask

ROOT = Path(__file__).resolve().parent.parent


def test_render_yaml_targets_wsgi_app():
    data = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    svc = data["services"][0]
    assert svc["startCommand"].split()[0] == "gunicorn"
    assert "web.app:app" in svc["startCommand"]
    assert "$PORT" in svc["startCommand"]
    assert svc["buildCommand"] == "pip install -r requirements.txt"


def test_requirements_has_gunicorn():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "gunicorn" in req


def test_app_importable_as_wsgi():
    from web.app import app
    assert isinstance(app, Flask)
