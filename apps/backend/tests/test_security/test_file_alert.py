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


def recording_gh(posted: Path) -> str:
    """Bash lines for a fake ``gh`` that appends each argument to ``posted``, one per
    line; the file after ``--body-file`` is appended by its contents, so a test reads
    the body the issue would get."""
    return (
        "previous=\n"
        'for argument in "$@"; do\n'
        '  if [ "$previous" = --body-file ]; then cat "$argument";'
        f' else printf "%s" "$argument"; fi >> {posted}\n'
        f"  echo >> {posted}; previous=$argument\n"
        "done\n"
    )


def _file(
    body: str | bytes, gh: str = "", **env: str
) -> tuple[subprocess.CompletedProcess[bytes], str]:
    run, posted, _ = _file_and_waits(body, gh, **env)
    return run, posted


def _file_and_waits(
    body: str | bytes, gh: str = "", **env: str
) -> tuple[subprocess.CompletedProcess[bytes], str, list[str]]:
    """Run the script with a ``gh`` that records its arguments, then runs ``gh``
    (a bash body: ``$1`` is the subcommand, ``$CALLS`` counts earlier calls), and a
    ``sleep`` that records how long it was asked to wait and returns at once."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        posted, calls = tmp / "posted.txt", tmp / "calls"
        calls.write_text("0")
        fake = tmp / "gh"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            f"CALLS=$(cat {calls}); echo $((CALLS + 1)) > {calls}\n"
            + recording_gh(posted)
            + gh
        )
        fake.chmod(0o755)
        waits = tmp / "waits"
        sleep = tmp / "sleep"
        sleep.write_text(f'#!/usr/bin/env bash\necho "$1" >> {waits}\n')
        sleep.chmod(0o755)
        run = subprocess.run(
            [str(SCRIPT), TITLE, PHRASE],
            input=body if isinstance(body, bytes) else body.encode(),
            env={
                **os.environ,
                "PATH": f"{tmp}:{os.environ['PATH']}",
                "HOST": "",
                "DEPLOY_USER": "",
                "DEPLOY_PATH": "",
                **env,
            },
            capture_output=True,
            timeout=30,
            check=False,
        )
        return (
            run,
            posted.read_text() if posted.exists() else "",
            waits.read_text().split() if waits.exists() else [],
        )


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


def test_a_host_inside_the_path_or_user_does_not_leave_the_rest():
    """The default path ends in `/staging`; a HOST of `staging` replaced first would
    publish `/srv/<staging host>-prod/app` and `<staging host>-ops@…`."""
    body = "cd: /srv/staging-prod/app: No such file\nstaging-ops@staging: denied\n"
    _, posted = _file(
        body,
        HOST="staging",
        DEPLOY_USER="staging-ops",
        DEPLOY_PATH="/srv/staging-prod/app",
    )
    assert "cd: <deploy path>: No such file" in posted
    assert "<deploy user>@<staging host>: denied" in posted
    assert "prod" not in posted and "-ops" not in posted


def test_a_path_set_with_a_trailing_slash_is_redacted_without_it():
    _, posted = _file("path /srv/app and /srv/app/x\n", DEPLOY_PATH="/srv/app/")
    assert "path <deploy path> and <deploy path>/x" in posted


def test_a_search_that_printed_before_failing_is_not_read_twice():
    """Only the successful attempt's output names the issue to comment on."""
    gh = '[ "$2" = list ] && echo 41\n[ "$CALLS" = 0 ] && exit 1\nexit 0\n'
    run, posted = _file("again\n", gh=gh)
    assert run.returncode == 0, run.stderr
    assert "comment\n41\n--body" in posted and "create" not in posted


def test_names_that_partly_overlap_are_redacted_as_one():
    """Replacing the path first broke the host's match: `<deploy path>-prod`."""
    _, posted = _file(
        "in /srv/application/node-prod now\n",
        HOST="node-prod",
        DEPLOY_PATH="/srv/application/node",
    )
    assert "in <deploy path> now" in posted


def test_a_name_that_overlaps_itself_is_redacted_whole():
    _, posted = _file("at node-node-node\n", HOST="node-node")
    assert "at <staging host>\n" in posted


def test_a_magicdns_name_does_not_publish_the_tailnet():
    """HOST is the bare machine name; the full name would leave `.tail1234.ts.net`."""
    body = "ssh: Could not resolve hostname box.tail1234.ts.net: failure\n"
    _, posted = _file(body, HOST="box")
    assert "hostname <tailnet address>: failure" in posted and "tail1234" not in posted


def test_an_address_before_a_colon_keeps_the_colon():
    """#1231 item 1: the colon after the address is ssh's, not the address's."""
    body = (
        "connect to fd7a:115c:a1e0::1: Connection refused\n"
        "fd7a:115c:a1e0:ab12::3:Cannot route\n"
        "bare fd7a:115c:a1e0:: here\n"
    )
    _, posted = _file(body)
    assert "connect to <tailnet address>: Connection refused" in posted
    assert "<tailnet address>:Cannot route" in posted
    assert "bare <tailnet address> here" in posted


def test_a_body_too_long_for_an_issue_is_cut_to_fit():
    """#1231 item 4: GitHub refuses a body over 65,536 characters, and Linux refuses
    an argument over 128 KiB, so the alert would be lost either way."""
    body = "first line\n" + "é" * 200_000 + "\nlast line\n"
    run, posted = _file(body)
    assert run.returncode == 0, run.stderr
    sent = posted.split("--body-file\n", 1)[1]
    assert sent.startswith("first line\n")
    assert "last line" not in sent
    assert 65_000 < len(sent) <= 65_536, "cut by characters, as GitHub counts"
    assert "characters were cut" in sent and "run log" in sent


def test_a_body_that_fits_is_sent_whole():
    run, posted = _file("short body\n")
    assert run.returncode == 0, run.stderr
    assert "short body" in posted and "cut" not in posted


def test_the_retry_waits_a_minute_by_default():
    """#1231 item 5: GitHub asks for at least a minute after a secondary rate limit."""
    run, _, waits = _file_and_waits("body\n", gh='[ "$CALLS" = 0 ] && exit 1\nexit 0\n')
    assert run.returncode == 0, run.stderr
    assert waits == ["60"]


def test_the_retry_wait_can_be_set():
    _, _, waits = _file_and_waits(
        "body\n",
        gh='[ "$CALLS" = 0 ] && exit 1\nexit 0\n',
        ALERT_RETRY_DELAY_SECONDS="7",
    )
    assert waits == ["7"]


def test_bytes_that_are_not_utf8_are_still_redacted_and_filed():
    """ssh stderr can hold any bytes; counting characters must not lose the alert."""
    run, posted = _file(b"bad \xff\xfe byte fd7a:115c:a1e0::1: refused\n")
    assert run.returncode == 0, run.stderr
    assert "byte <tailnet address>: refused" in posted and "fd7a" not in posted


def test_a_name_with_a_non_ascii_character_is_redacted():
    """The body is decoded to count characters; the names must be decoded with it."""
    _, posted = _file(
        "cd /srv/café: no such file\nssh: connect to höst port 22\n",
        HOST="höst",
        DEPLOY_PATH="/srv/café",
    )
    assert "cd <deploy path>: no such file" in posted
    assert "connect to <staging host> port 22" in posted
