"""Tests for the plan command (generate_plan / display_plan / cmd_plan)."""

from pathlib import Path
from unittest.mock import Mock, patch

from kubeman import KubernetesResource, TemplateRegistry
from kubeman.cli import generate_plan, display_plan, cmd_plan


class _DemoResource(KubernetesResource):
    def __init__(self):
        super().__init__()
        self.name = "demo-app"
        self.namespace = "demo"
        self.add_configmap(name="cfg", namespace="demo", data={"k": "v"})


class _BuildingResource(KubernetesResource):
    def __init__(self):
        super().__init__()
        self.name = "builder"
        self.namespace = "demo"
        self.add_configmap(name="b", namespace="demo", data={"k": "v"})

    def build(self):
        pass

    def load(self):
        pass


class TestGeneratePlan:
    def test_empty_registry(self):
        TemplateRegistry.clear()
        plan = generate_plan()
        assert plan["template_names"] == []
        assert plan["total_manifests"] == 0

    def test_renders_into_given_dir_and_categorizes(self, tmp_path):
        TemplateRegistry.clear()
        TemplateRegistry.register(_DemoResource)
        plan = generate_plan(manifests_dir=tmp_path)
        assert plan["template_names"] == ["demo-app"]
        assert plan["total_manifests"] >= 1
        # Rendered into the provided dir.
        assert list(tmp_path.rglob("*.yaml"))

    def test_detects_build_and_load(self, tmp_path):
        TemplateRegistry.clear()
        TemplateRegistry.register(_BuildingResource)
        plan = generate_plan(manifests_dir=tmp_path)
        assert plan["templates_with_build"] == ["builder"]
        assert plan["templates_with_load"] == ["builder"]

    def test_manifest_paths_are_relative(self, tmp_path):
        TemplateRegistry.clear()
        TemplateRegistry.register(_DemoResource)
        plan = generate_plan(manifests_dir=tmp_path)
        files = plan["manifest_files"]
        all_paths = files["crd_files"] + files["namespace_files"] + files["other_files"]
        assert all_paths
        assert all(not Path(p).is_absolute() for p in all_paths if not p.startswith("(extracted"))


class TestDisplayPlan:
    def test_smoke(self, capsys):
        plan = {
            "templates_with_build": ["a"],
            "templates_with_load": [],
            "template_names": ["a"],
            "manifest_files": {
                "crd_files": [],
                "namespace_files": [],
                "other_files": ["a/a-configmap.yaml"],
            },
            "total_manifests": 1,
        }
        display_plan(plan, verbose=True)
        assert "PLAN" in capsys.readouterr().out


class TestCmdPlan:
    def test_does_not_write_to_user_dir(self, tmp_path):
        """plan renders into a temp dir, leaving the user's tree untouched."""
        TemplateRegistry.clear()

        def fake_load(_):
            TemplateRegistry.register(_DemoResource)

        out_dir = tmp_path / "manifests"
        out_dir.mkdir()
        with patch("kubeman.cli.load_templates_file", side_effect=fake_load):
            args = Mock(file="k.py", output_dir=str(out_dir), verbose=False, skip_build=True)
            cmd_plan(args)

        assert list(out_dir.rglob("*.yaml")) == []
