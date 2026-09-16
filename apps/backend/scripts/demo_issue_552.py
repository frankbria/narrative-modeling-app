"""Demo for #552: per-secret consumers derived from the real compose file vs the rotation runbook."""
import re

compose = open("docker-compose.staging.yml").read()
runbook = open("docs/operations/CREDENTIAL_ROTATION.md").read()
backend, frontend = compose.split("\n  frontend:")[0], compose.split("\n  frontend:")[1]
secrets = sorted({v for v in re.findall(r"\$\{([A-Z][A-Z0-9_]+)", compose)
                  if re.search(r"SECRET|KEY|PASSWORD|URI|TOKEN|DSN", v)})
print(f"{'secret':24s} backend frontend in-runbook")
for v in secrets:
    print(f"{v:24s} {'yes' if v in backend else 'no ':7s} {'yes' if v in frontend else 'no ':8s} {'yes' if f'`{v}`' in runbook else 'NO'}")
