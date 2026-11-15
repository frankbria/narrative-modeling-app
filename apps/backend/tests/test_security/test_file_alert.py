"""#1215: the one way a scheduled workflow files its failure on a public issue.

``scripts/ci/file_alert.sh`` is called by ``staging-health.yml`` and
``subscription-reconcile.yml``. GitHub masks secrets in the run log, never in an
issue body the run posts itself (#1150), and a ``gh`` call that fails once must not
leave a red run as the only signal that day. These tests run the real script
against a fake ``gh``.
"""

import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "file_alert.sh"
TITLE = "[P2] [billing] Subscription reconciliation is failing"
PHRASE = "Subscription reconciliation is failing"


def _file(
    body: str, gh: str = "", **env: str
) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run the script with a ``gh`` that records its arguments, then runs ``gh``
    (a bash body: ``$1`` is the subcommand, ``$CALLS`` counts earlier calls)."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        posted, calls = tmp / "posted.txt", tmp / "calls"
        calls.write_text("0")
        fake = tmp / "gh"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            f"CALLS=$(cat {calls}); echo $((CALLS + 1)) > {calls}\n"
            f'printf "%s\\n" "$@" >> {posted}\n' + gh
        )
        fake.chmod(0o755)
        run = subprocess.run(
            [str(SCRIPT), TITLE, PHRASE],
            input=body,
            env={
                **os.environ,
                "PATH": f"{tmp}:{os.environ['PATH']}",
                "ALERT_RETRY_DELAY_SECONDS": "0",
                "HOST": "",
                "DEPLOY_USER": "",
                "DEPLOY_PATH": "",
                **env,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return run, posted.read_text() if posted.exists() else ""


def test_a_first_failure_opens_an_issue_with_the_title_and_body():
    run, posted = _file("the body\n")
    assert run.returncode == 0, run.stderr
    assert f'"{PHRASE}" in:title' in posted
    assert "create" in posted and TITLE in posted and "the body" in posted


def test_a_later_failure_comments_on_the_oldest_open_alert():
    run, posted = _file(
        "again\n", gh='[ "$2" = list ] && [ "$CALLS" = 0 ] && echo 41\nexit 0\n'
    )
    assert run.returncode == 0, run.stderr
    assert "min_by(.number).number // empty" in posted
    assert "comment\n41\n" in posted and "create" not in posted


def test_a_gh_call_that_fails_once_is_retried():
    """Item 6: one failed `gh` call must not lose the day's alert."""
    run, posted = _file("body\n", gh='[ "$CALLS" = 0 ] && exit 1\nexit 0\n')
    assert run.returncode == 0, run.stderr
    assert posted.count("create") == 1 and posted.count("list") == 2


def test_a_gh_call_that_fails_twice_fails_the_step():
    run, posted = _file("body\n", gh="exit 1\n")
    assert run.returncode != 0
    assert posted.count("list") == 2 and "create" not in posted


def test_the_box_names_never_reach_the_issue():
    """ssh names the user and host (lowercased) in its errors, the state dump names
    the path, and another tool can print the user without an `@`."""
    body = (
        "deployer@box-name: Permission denied (publickey).\n"
        "cannot cd to /srv/secret-path\n"
        "chown: invalid user: 'deployer'\n"
    )
    run, posted = _file(
        body, HOST="Box-Name", DEPLOY_USER="deployer", DEPLOY_PATH="/srv/secret-path"
    )
    assert run.returncode == 0, run.stderr
    assert "<deploy user>@<staging host>: Permission denied" in posted
    assert "cannot cd to <deploy path>" in posted
    assert "invalid user: '<deploy user>'" in posted
    for secret in ("box-name", "deployer", "/srv/secret-path"):
        assert secret not in posted.lower()


def test_the_default_user_is_redacted_only_beside_the_host():
    """`root` is the public default; as a bare word it is ordinary text."""
    body = "root@box: denied\nthe root cause is the key\n"
    _, posted = _file(body, HOST="box", DEPLOY_USER="root")
    assert "<deploy user>@<staging host>: denied" in posted
    assert "the root cause is the key" in posted


def test_a_tailnet_address_never_reaches_the_issue():
    """ssh can print the box's tailnet address instead of its name (item 3)."""
    body = (
        "ssh: connect to host 100.101.102.103 port 22: Connection timed out\n"
        "ssh: connect to host fd7a:115c:a1e0::1234:abcd port 22: No route\n"
        "edge cases: 100.64.0.1, 100.127.255.254.\n"
        "not tailnet: 100.63.0.1 100.128.0.1 10.100.64.1 version 1100.64.0.1\n"
    )
    run, posted = _file(body)
    assert run.returncode == 0, run.stderr
    assert "connect to host <tailnet address> port 22: Connection timed out" in posted
    assert "connect to host <tailnet address> port 22: No route" in posted
    assert "edge cases: <tailnet address>, <tailnet address>." in posted
    for address in ("100.101.102.103", "fd7a:115c", "100.64.0.1,", "100.127.255.254"):
        assert address not in posted
    assert (
        "not tailnet: 100.63.0.1 100.128.0.1 10.100.64.1 version 1100.64.0.1" in posted
    )


def test_an_unset_value_redacts_nothing():
    body = "a@b and /srv and text\n"
    _, posted = _file(body)
    assert body.strip() in posted
