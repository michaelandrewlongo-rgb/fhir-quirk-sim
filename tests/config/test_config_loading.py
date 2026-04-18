"""SimulatorConfig load + round-trip tests."""
from pathlib import Path

import pytest

from epic_sim.config import SimulatorConfig


CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


class TestDefaults:
    def test_instantiates_with_no_args(self):
        cfg = SimulatorConfig()
        assert cfg.backend_services_jwt_required is True
        assert cfg.auth_code_format == "jwt"
        assert cfg.jwt_jti_max_length == 151
        assert cfg.post_filter_discard_rate == pytest.approx(0.3)
        assert cfg.fhir_versions_active == ["R4"]
        # Sim plumbing flag defaults off so Phase 1 behavior is preserved.
        assert cfg.auth_required is False


class TestYamlLoading:
    def test_loads_default_yaml(self):
        cfg = SimulatorConfig.from_yaml(CONFIGS_DIR / "default.yaml")
        assert isinstance(cfg, SimulatorConfig)
        assert cfg.auth_required is False

    def test_loads_strict_epic_yaml(self):
        cfg = SimulatorConfig.from_yaml(CONFIGS_DIR / "strict_epic.yaml")
        assert cfg.auth_required is True
        assert cfg.backend_services_jwt_required is True
        assert cfg.post_filter_enabled is True
        assert cfg.include_iterate_supported is False
        assert cfg.populate_meta_last_updated is False
        assert cfg.binary_403_rate == pytest.approx(0.05)

    def test_loads_permissive_yaml(self):
        cfg = SimulatorConfig.from_yaml(CONFIGS_DIR / "permissive.yaml")
        assert cfg.auth_required is False
        assert cfg.backend_services_jwt_required is False
        assert cfg.include_iterate_supported is True
        assert cfg.populate_meta_last_updated is True
        assert cfg.fhir_id_format == "uuid"
        assert cfg.appointment_create_supported is True


class TestEnvLoading:
    def test_from_env_returns_defaults_when_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("EPIC_SIM_CONFIG", raising=False)
        cfg = SimulatorConfig.from_env()
        assert cfg.auth_required is False

    def test_from_env_loads_path(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("EPIC_SIM_CONFIG", str(CONFIGS_DIR / "strict_epic.yaml"))
        cfg = SimulatorConfig.from_env()
        assert cfg.auth_required is True


class TestAppIntegration:
    def test_create_app_wires_default_config(self):
        from epic_sim.app import create_app

        app = create_app()
        assert isinstance(app.state.config, SimulatorConfig)
        assert app.state.config.auth_required is False

    def test_create_app_accepts_custom_config(self):
        from epic_sim.app import create_app

        cfg = SimulatorConfig(auth_required=True, post_filter_discard_rate=0.1)
        app = create_app(config=cfg)
        assert app.state.config is cfg
        assert app.state.config.post_filter_discard_rate == pytest.approx(0.1)
