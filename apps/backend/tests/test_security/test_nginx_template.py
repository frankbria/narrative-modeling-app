"""The edge config is rendered and applied by a script, not by `nano` (#594).

`nginx-staging.conf` was applied to the box by hand, so the live file drifted for
two months and every edge concern the repo file thinks it owns — the #273 request-id
map, the security headers, #768's auth rate limit — was in git and had never run.
Worse, #456 could have been "fixed" by editing the repo file and merging green while
staging kept dropping every Stripe event.

What made a repeatable apply impossible was the placeholders: the file carried
`narrative.yourdomain.com` and matching Let's Encrypt paths that fail `nginx -t`, so
it could only ever be hand-edited. These tests pin the two halves of the fix — the
config is fully parameterised, and something actually applies it.
"""

import re
import subprocess

from tests.test_security.test_nginx_webhook_route import NGINX_CONF, REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "deploy" / "apply_nginx_conf.sh"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"


def _declared_vars() -> set[str]:
    """The placeholders the render step substitutes, read from the script itself."""
    m = re.search(r"^SUBST_VARS=\(([^)]*)\)", SCRIPT.read_text(), re.M)
    assert m, "apply_nginx_conf.sh must declare `SUBST_VARS=(...)`"
    return set(m.group(1).split())


class TestConfigIsParameterised:
    def test_no_placeholder_domain_survives(self):
        text = NGINX_CONF.read_text()
        assert "yourdomain.com" not in text
        assert "REPLACE" not in text

    def test_server_name_is_a_variable(self):
        names = re.findall(r"^\s*server_name\s+(.+?);", NGINX_CONF.read_text(), re.M)
        assert names, "expected at least one server_name"
        assert all("${NGINX_SERVER_NAME}" in n for n in names), names

    def test_certificate_paths_are_variables(self):
        certs = re.findall(
            r"^\s*ssl_(?:certificate|certificate_key|trusted_certificate)\s+(\S+);",
            NGINX_CONF.read_text(),
            re.M,
        )
        assert len(certs) == 3, certs
        assert all(c.startswith("${NGINX_CERT_DIR}/") for c in certs), certs

    def test_every_placeholder_is_one_the_script_renders(self):
        # A `${VAR}` the render step does not know about reaches live nginx
        # literally, which is a config error at best and a wrong cert path at worst.
        used = set(re.findall(r"\$\{(\w+)\}", NGINX_CONF.read_text()))
        assert used, "expected the config to carry placeholders"
        assert used <= _declared_vars(), used - _declared_vars()


class TestSomethingAppliesIt:
    def test_the_deploy_workflow_runs_the_script(self):
        # The step must actually invoke it, not merely mention it in a comment.
        text = DEPLOY_WORKFLOW.read_text()
        step = re.search(
            r"^      - name: Apply nginx edge config$(.*?)(?=^      - name: )",
            text,
            re.S | re.M,
        )
        assert step, "expected an `Apply nginx edge config` step in deploy.yml"
        assert "apply_nginx_conf.sh" in step.group(1)

    def test_the_apply_runs_before_the_health_check(self):
        # Ordering is load-bearing: a broken edge must fail the deploy, and the
        # health check probes through the app rather than the edge, so a later apply
        # would report a green deploy over a config that never passed `nginx -t`.
        text = DEPLOY_WORKFLOW.read_text()
        assert text.index("- name: Apply nginx edge config") < text.index(
            "- name: Health check"
        )

    def test_script_self_check_passes(self):
        # The script's own assertions: rendering leaves nginx's `$variables` alone,
        # an unset hostname is a no-op, and a failed `nginx -t` restores the backup.
        subprocess.run(["bash", str(SCRIPT), "--self-check"], check=True, timeout=60)
