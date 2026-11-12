"""#831: the images are built once, in CI, and every box runs them by digest.

Production has to be "staging moved over". That is only true if production runs the
image staging tested, which needs three things these tests pin:

* nothing on the deploy path builds (`--build`, a compose `build:` block);
* the frontend image is given no host-specific value at build time;
* one compose file serves both environments, with the environment's name, the image
  digests and the version supplied by `scripts/deploy/compose.sh`.

The scripts are run for real against a fake `docker` (and `git`) that records what it
was asked to do; the compose file is rendered by the real `docker compose`.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.test_security.deploy_box import REPO_ROOT, stand_in_box

COMPOSE_FILE = REPO_ROOT / "docker-compose.deploy.yml"
FRONTEND_DOCKERFILE = REPO_ROOT / "apps/frontend/Dockerfile"
BUILD_SCRIPT = REPO_ROOT / "scripts/ci/build_images.sh"
DEPLOY_SCRIPT = REPO_ROOT / "scripts/deploy/deploy_images.sh"
DEPLOY_WORKFLOW = REPO_ROOT / ".github/workflows/deploy.yml"
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"
BOX_WORKFLOWS = [
    DEPLOY_WORKFLOW,
    REPO_ROOT / ".github/workflows/staging-health.yml",
    REPO_ROOT / ".github/workflows/subscription-reconcile.yml",
]

BACKEND = "ghcr.io/frankbria/narrative-modeling-app/backend@sha256:" + "a" * 64
FRONTEND = "ghcr.io/frankbria/narrative-modeling-app/frontend@sha256:" + "b" * 64
COMMIT = "c8c9ecca0000000000000000000000000000beef"

# The one required value both templates leave blank for the operator to fill in.
A_DSN = "\nSENTRY_DSN=https://key@sentry.example/1\n"

# Appends one line per call (`docker <args>`), then does what the test scripted.
RECORDING = '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "$CALLS"\n'


def _code_lines(path: Path) -> str:
    return "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("#"))


def _fake_tools(directory: Path, docker_script: str = "") -> Path:
    bin_dir = directory / "bin"
    bin_dir.mkdir()
    for name, script in (("docker", docker_script), ("git", "")):
        (bin_dir / name).write_text(RECORDING + script)
        (bin_dir / name).chmod(0o755)
    return bin_dir


def _run(command: list[str], box: Path, bin_dir: Path, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        env={
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "HOME": str(box),
            "CALLS": str(box / "calls"),
            "DEPLOY_PATH": str(box),
            **extra,
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _calls(box: Path) -> list[str]:
    calls = box / "calls"
    return calls.read_text().splitlines() if calls.exists() else []


# ── nothing on the deploy path builds ────────────────────────────────────────


def test_no_service_is_built_on_the_box():
    services = yaml.safe_load(COMPOSE_FILE.read_text())["services"]

    assert {name: "build" in service for name, service in services.items()} == {
        "backend": False,
        "frontend": False,
        "redis": False,
    }
    assert services["backend"]["image"].startswith("${BACKEND_IMAGE:?")
    assert services["frontend"]["image"].startswith("${FRONTEND_IMAGE:?")


def test_no_workflow_or_deploy_script_asks_compose_to_build():
    paths = [*BOX_WORKFLOWS, *sorted((REPO_ROOT / "scripts/deploy").glob("*.sh"))]
    building = [path.name for path in paths if re.search(r"--build\b|\bcompose\b.*\bbuild\b", _code_lines(path))]
    assert building == []


def test_every_compose_call_on_a_box_goes_through_the_wrapper():
    """A bare `docker compose -f …` has no ENVIRONMENT and no image, and fails on the
    file's guards. One caller, so the next step copies a working one."""
    paths = [*BOX_WORKFLOWS, *sorted((REPO_ROOT / "scripts/deploy").glob("*.sh"))]
    bare = [
        path.name
        for path in paths
        if path.name != "compose.sh" and re.search(r"docker compose\s+-f", _code_lines(path))
    ]
    assert bare == []


# ── the frontend image is host-agnostic ──────────────────────────────────────


def test_no_host_specific_value_is_a_frontend_build_arg():
    """A `NEXT_PUBLIC_*` value given to `next build` is inlined into the bundle, and the
    image then carries one host's API address onto the other."""
    dockerfile = _code_lines(FRONTEND_DOCKERFILE)
    assert re.findall(r"^\s*(?:ARG|ENV)\s+NEXT_PUBLIC_\w+", dockerfile, re.MULTILINE) == []

    for path in (BUILD_SCRIPT, DEPLOY_WORKFLOW, CI_WORKFLOW, COMPOSE_FILE):
        assert not re.search(r"build-arg[ =\"']*NEXT_PUBLIC_", _code_lines(path)), path.name
    build_args = set(re.findall(r'--build-arg "(\w+)=', BUILD_SCRIPT.read_text()))
    assert build_args == {"SENTRY_RELEASE", "SENTRY_ORG", "SENTRY_PROJECT"}


def test_the_frontend_container_is_given_its_public_settings_at_run_time():
    environment = yaml.safe_load(COMPOSE_FILE.read_text())["services"]["frontend"]["environment"]

    assert environment["NEXT_PUBLIC_API_URL"] == "${NEXT_PUBLIC_API_URL:?}"
    assert environment["NEXT_PUBLIC_SENTRY_DSN"] == "${SENTRY_DSN:?}"
    assert environment["NEXT_PUBLIC_SENTRY_ENVIRONMENT"] == "${ENVIRONMENT}"


def test_the_pr_gate_builds_both_images_and_checks_one_serves_two_hosts():
    ci = yaml.safe_load(CI_WORKFLOW.read_text())
    runs = "\n".join(step.get("run", "") for step in ci["jobs"]["docker-images"]["steps"])

    assert "scripts/ci/build_images.sh ci" in runs
    assert "scripts/ci/check_frontend_image_is_host_agnostic.sh narrative-frontend:ci" in runs
    assert "docker-images" in ci["jobs"]["ci-success"]["needs"]


# ── one compose file, both environments ──────────────────────────────────────


def test_the_compose_file_names_no_environment():
    # NODE_ENV is the build mode of the Next.js server, the same on every host.
    code = _code_lines(COMPOSE_FILE).replace("NODE_ENV: production", "")
    assert re.findall(r".*\b(?:staging|production)\b.*", code) == []


def _rendered(tmp_path: Path, env_file: str) -> dict:
    """What the real `docker compose` makes of the file on a box provisioned from the template."""
    box = stand_in_box(tmp_path / env_file.removeprefix(".env."), env_file)
    shutil.copy2(COMPOSE_FILE, box / COMPOSE_FILE.name)
    template = (REPO_ROOT / f"{env_file}.example").read_text()
    # The template's hand-run pitfalls: a line a box could carry over from before #831.
    (box / env_file).write_text(template + A_DSN + "ENVIRONMENT=the-other-one\nAPP_VERSION=stale\n")
    (box / ".deploy-images.env").write_text(f"APP_VERSION={COMMIT}\nBACKEND_IMAGE={BACKEND}\nFRONTEND_IMAGE={FRONTEND}\n")
    run = subprocess.run(
        [str(box / "scripts/deploy/compose.sh"), "config", "--format", "json"],
        env={"PATH": os.environ["PATH"], "HOME": str(box), "DEPLOY_PATH": str(box)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_the_env_files_name_decides_the_environment(tmp_path, environment):
    config = _rendered(tmp_path, f".env.{environment}")
    backend, frontend = config["services"]["backend"], config["services"]["frontend"]

    assert backend["environment"]["ENVIRONMENT"] == environment
    assert frontend["environment"]["ENVIRONMENT"] == environment
    assert frontend["environment"]["NEXT_PUBLIC_SENTRY_ENVIRONMENT"] == environment
    assert {name: service["container_name"] for name, service in config["services"].items()} == {
        "backend": f"narrative-{environment}-backend",
        "frontend": f"narrative-{environment}-frontend",
        "redis": f"narrative-{environment}-redis",
    }
    assert config["networks"]["narrative-network"]["name"] == f"narrative-{environment}-network"


def test_both_environments_run_the_recorded_digests_and_report_the_commit(tmp_path):
    staging = _rendered(tmp_path, ".env.staging")["services"]
    production = _rendered(tmp_path, ".env.production")["services"]

    for services in (staging, production):
        assert (services["backend"]["image"], services["frontend"]["image"]) == (BACKEND, FRONTEND)
        assert services["backend"]["environment"]["APP_VERSION"] == COMMIT
    # The frontend's API base is each host's own, from its env file.
    assert staging["frontend"]["environment"]["NEXT_PUBLIC_API_URL"] != production["frontend"]["environment"]["NEXT_PUBLIC_API_URL"]


def test_the_wrapper_refuses_a_box_with_no_env_file_or_with_both(tmp_path):
    neither = stand_in_box(tmp_path / "neither")
    (neither / ".env.staging").unlink()
    both = stand_in_box(tmp_path / "both")
    (both / ".env.production").write_text("")

    for box in (neither, both):
        run = _run([str(box / "scripts/deploy/compose.sh"), "ps"], box, _fake_tools(box))
        assert run.returncode == 2
        assert "exactly one of .env.staging or .env.production" in run.stderr
        assert _calls(box) == []


def test_a_box_with_no_recorded_images_can_be_probed_but_not_started(tmp_path):
    """The first deploy after #831 failing part way must not blind the health probe, and
    must not let a hand-run `up` start an image nobody chose."""
    box = stand_in_box(tmp_path)
    bin_dir = _fake_tools(box)
    wrapper = str(box / "scripts/deploy/compose.sh")

    probe = _run([wrapper, "exec", "-T", "backend", "python", "-m", "app.health_probe"], box, bin_dir)
    assert probe.returncode == 0, probe.stderr
    assert _calls(box) == [
        "docker compose -f docker-compose.deploy.yml --env-file .env.staging exec -T backend python -m app.health_probe"
    ]

    for starting in (["up", "-d", "--force-recreate"], ["pull"], ["run", "backend"]):
        refused = _run([wrapper, *starting], box, bin_dir)
        assert refused.returncode == 2, starting
        assert "run a deploy" in refused.stderr
    assert len(_calls(box)) == 1


# ── the deploy pulls digests and records what it started ─────────────────────


def _deploy(box: Path, docker_script: str = "", **overrides: str) -> subprocess.CompletedProcess:
    for name in ("deploy_images.sh", "preflight_staging_env.sh"):
        shutil.copy2(REPO_ROOT / "scripts/deploy" / name, box / "scripts/deploy" / name)
    shutil.copy2(COMPOSE_FILE, box / COMPOSE_FILE.name)
    (box / ".env.staging").write_text((REPO_ROOT / ".env.staging.example").read_text() + A_DSN)
    values = {
        "APP_VERSION": COMMIT,
        "BACKEND_IMAGE": BACKEND,
        "FRONTEND_IMAGE": FRONTEND,
        "REGISTRY_USER": "deployer",
        "REGISTRY_TOKEN": "ghs_short_lived",
        **overrides,
    }
    return _run(["bash", str(DEPLOY_SCRIPT)], box, _fake_tools(box, docker_script), **values)


def test_a_deploy_checks_out_the_commit_pulls_the_digests_and_records_them(tmp_path):
    box = stand_in_box(tmp_path)

    run = _deploy(box)

    assert run.returncode == 0, run.stderr
    compose = "docker compose -f docker-compose.deploy.yml --env-file .env.staging"
    assert _calls(box) == [
        "git fetch --prune origin",
        "git checkout main",
        f"git reset --hard {COMMIT}",
        "docker login ghcr.io --username deployer --password-stdin",
        f"{compose} pull --quiet backend frontend",
        f"{compose} up -d --remove-orphans",
        f"{compose} ps",
        "docker logout ghcr.io",
    ]
    assert (box / ".deploy-images.env").read_text() == (
        f"APP_VERSION={COMMIT}\nBACKEND_IMAGE={BACKEND}\nFRONTEND_IMAGE={FRONTEND}\n"
    )
    assert "ghs_short_lived" not in (box / "calls").read_text(), "the token was on a command line"


def test_a_failed_pull_starts_nothing_records_nothing_and_still_logs_out(tmp_path):
    box = stand_in_box(tmp_path)
    (box / ".deploy-images.env").write_text("APP_VERSION=previous\nBACKEND_IMAGE=old@sha256:1\nFRONTEND_IMAGE=old@sha256:2\n")

    run = _deploy(box, 'case " $* " in *" pull "*) echo "denied" >&2; exit 1;; esac\n')

    assert run.returncode != 0
    calls = _calls(box)
    assert not any(" up " in call for call in calls)
    assert calls[-1] == "docker logout ghcr.io"
    assert "APP_VERSION=previous" in (box / ".deploy-images.env").read_text(), (
        "the record must keep naming what is still running"
    )


def test_a_failed_start_does_not_record_the_new_images(tmp_path):
    box = stand_in_box(tmp_path)

    run = _deploy(box, 'case " $* " in *" up "*) exit 1;; esac\n')

    assert run.returncode != 0
    assert not (box / ".deploy-images.env").exists()


def test_a_tag_is_refused_before_anything_runs(tmp_path):
    """A tag can be pushed over between staging's deploy and production's; a digest cannot."""
    box = stand_in_box(tmp_path)

    run = _deploy(box, BACKEND_IMAGE="ghcr.io/frankbria/narrative-modeling-app/backend:main")

    assert run.returncode == 2
    assert "not a digest reference" in run.stderr
    assert _calls(box) == []


def test_a_box_missing_a_required_setting_is_refused_before_the_pull(tmp_path):
    box = stand_in_box(tmp_path)
    for name in ("deploy_images.sh", "preflight_staging_env.sh"):
        shutil.copy2(REPO_ROOT / "scripts/deploy" / name, box / "scripts/deploy" / name)
    shutil.copy2(COMPOSE_FILE, box / COMPOSE_FILE.name)
    template = (REPO_ROOT / ".env.staging.example").read_text()
    (box / ".env.staging").write_text(re.sub(r"(?m)^NEXT_PUBLIC_API_URL=.*$", "NEXT_PUBLIC_API_URL=", template) + A_DSN)

    run = _run(
        ["bash", str(DEPLOY_SCRIPT)],
        box,
        _fake_tools(box),
        APP_VERSION=COMMIT,
        BACKEND_IMAGE=BACKEND,
        FRONTEND_IMAGE=FRONTEND,
    )

    assert run.returncode == 1
    assert "- NEXT_PUBLIC_API_URL" in run.stderr
    assert not any(call.startswith("docker") for call in _calls(box))


# ── CI builds once and hands the digests to the deploy ───────────────────────


def _build(tmp_path: Path, *args: str, **extra: str) -> tuple[subprocess.CompletedProcess, list[str]]:
    digest = 'case " $* " in *" inspect "*) echo "registry.example/app/${!###*/}@sha256:feed" | sed "s/:[^@]*@/@/";; esac\n'
    run = _run(["bash", str(BUILD_SCRIPT), *args], tmp_path, _fake_tools(tmp_path, digest), **extra)
    return run, _calls(tmp_path)


def test_the_pr_gate_builds_both_images_and_pushes_nothing(tmp_path):
    run, calls = _build(tmp_path, "ci")

    assert run.returncode == 0, run.stderr
    assert [call.split()[1] for call in calls] == ["build", "build"]
    assert "--tag narrative-backend:ci" in calls[0] and calls[0].endswith("/apps/backend")
    assert "--tag narrative-frontend:ci" in calls[1] and calls[1].endswith("/apps/frontend")
    assert run.stdout == ""


def test_a_push_prints_the_two_digest_references_and_nothing_else(tmp_path):
    """stdout goes straight into $GITHUB_OUTPUT: a stray line there is a broken output."""
    run, calls = _build(tmp_path, COMMIT, "--push", "registry.example/app")

    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == [
        "backend=registry.example/app/backend@sha256:feed",
        "frontend=registry.example/app/frontend@sha256:feed",
    ]
    assert [call.split()[1] for call in calls] == ["build", "build", "push", "push", "image", "image"]
    assert f"docker push registry.example/app/backend:{COMMIT}" in calls
    for call in calls[:2]:
        assert f"--label org.opencontainers.image.revision={COMMIT}" in call, "the image must say which commit it is"


def test_the_source_map_token_is_a_build_secret_only_when_it_is_set(tmp_path):
    (tmp_path / "without").mkdir()
    (tmp_path / "with").mkdir()
    without, calls_without = _build(tmp_path / "without", "ci")
    with_token, calls_with = _build(tmp_path / "with", "ci", SENTRY_AUTH_TOKEN="sntrys_token")

    assert (without.returncode, with_token.returncode) == (0, 0)
    assert "--secret" not in " ".join(calls_without)
    assert "--secret id=sentry_auth_token,env=SENTRY_AUTH_TOKEN" in calls_with[1]
    assert "--secret" not in calls_with[0], "the backend build has no use for it"
    assert "sntrys_token" not in " ".join(calls_with)


def test_the_deploy_job_deploys_what_the_build_job_built():
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text())
    build, deploy = workflow["jobs"]["build-images"], workflow["jobs"]["deploy-staging"]

    # `on` parses as YAML's boolean true.
    assert workflow[True]["push"] == {"branches": ["main"]}
    assert build["permissions"] == {"contents": "read", "packages": "write"}
    assert deploy["needs"] == "build-images"
    assert deploy["permissions"] == {"contents": "read", "packages": "read"}, (
        "the token the box is handed can read packages and nothing more"
    )
    assert workflow["permissions"] == {}

    step = next(step for step in deploy["steps"] if step.get("name") == "Deploy over SSH")
    assert step["env"]["BACKEND_IMAGE"] == "${{ needs.build-images.outputs.backend }}"
    assert step["env"]["FRONTEND_IMAGE"] == "${{ needs.build-images.outputs.frontend }}"
    assert step["env"]["APP_VERSION"] == "${{ github.sha }}"
    assert set(step["env"]["ON_BOX_FORWARD"].split()) == {
        "APP_VERSION",
        "BACKEND_IMAGE",
        "FRONTEND_IMAGE",
        "REGISTRY_USER",
        "REGISTRY_TOKEN",
    }
    assert "scripts/deploy/on_box.sh scripts/deploy/deploy_images.sh" in step["run"]
    assert "GITHUB_STEP_SUMMARY" in step["run"], "the deployed digests belong in the run summary"
