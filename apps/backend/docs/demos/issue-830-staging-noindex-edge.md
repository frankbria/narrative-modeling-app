# Issue #830: staging is noindex at the edge, production is not

*2026-10-11T00:19:49Z by Showboat 0.6.1*
<!-- showboat-id: 55290bd4-f02c-4812-bde2-4453b077d35d -->

Scope of this PR is AC4 of #830: every response from the staging server block carries `X-Robots-Tag: noindex, nofollow`, set in nginx, pinned by a test, and guarded so it applies only to staging. Production (#832) will render this same template, so the guard is a `map` on the hostname. The other criteria (certificate, `.env.staging`, OAuth and Stripe callbacks, retiring the old name) are box and console steps recorded on the issue.

The test in `tests/test_security/` and its siblings, against the real template:

```bash
cd apps/backend && PYTHONPATH=. uv run pytest tests/test_security/test_nginx_noindex.py -p no:cacheprovider -q -rA 2>&1 | grep -E "^(PASSED|FAILED)"; printf "all nginx edge tests: "; PYTHONPATH=. uv run pytest tests/test_security -k nginx -p no:cacheprovider -q -rA 2>&1 | grep -E "^(PASSED|FAILED)" | cut -d" " -f1 | sort | uniq -c | xargs
```

```output
PASSED tests/test_security/test_nginx_noindex.py::test_every_host_is_noindex_by_default
PASSED tests/test_security/test_nginx_noindex.py::test_only_the_production_hosts_are_indexable
PASSED tests/test_security/test_nginx_noindex.py::test_every_server_block_sends_the_header
PASSED tests/test_security/test_nginx_noindex.py::test_nothing_nested_drops_the_inherited_headers
PASSED tests/test_security/test_nginx_noindex.py::test_no_header_is_set_for_the_whole_shared_box
all nginx edge tests: 32 PASSED
```

CI has no nginx binary, so those tests read the template as text. To show the behaviour itself, this script renders the template through `apply_nginx_conf.sh` (the deploy path) for one hostname, loads it into a real nginx container with stub upstreams, and prints the headers each kind of response carries.

```bash
cat /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2d91ea4d-eae7-4965-83d9-6e57760de90d/scratchpad/edge830.sh
```

```output
#!/usr/bin/env bash
# Render nginx-staging.conf through apply_nginx_conf.sh for one hostname, load it
# into a real nginx with stub upstreams, and print the headers each path answers with.
# usage: edge830.sh <repo-root> <server-name>
set -euo pipefail
REPO="$1"; NAME="$2"
W="$(mktemp -d)"; mkdir "$W/certs"
trap 'docker rm -f edge830 >/dev/null 2>&1 || true; rm -rf "$W"' EXIT

printf 'NGINX_SERVER_NAME=%s\nNGINX_CERT_DIR=/certs\n' "$NAME" > "$W/env"
NGINX_CONF_SRC="$REPO/nginx-staging.conf" NGINX_ENV_FILE="$W/env" NGINX_TARGET="$W/site.conf" \
  NGINX_TEST_CMD=true NGINX_RELOAD_CMD=true bash "$REPO/scripts/deploy/apply_nginx_conf.sh" >/dev/null

openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$NAME" \
  -keyout "$W/certs/privkey.pem" -out "$W/certs/fullchain.pem" 2>/dev/null
cp "$W/certs/fullchain.pem" "$W/certs/chain.pem"

# Stand-ins for Next.js (which sets its own Cache-Control) and the backend.
cat > "$W/upstreams.conf" <<'EOF'
server { listen 127.0.0.1:3011; location / { add_header Cache-Control "public, max-age=31536000, immutable"; return 200 "frontend\n"; } }
server { listen 127.0.0.1:8010; location / { return 404 "backend\n"; } }
EOF
chmod -R a+rX "$W"

docker rm -f edge830 >/dev/null 2>&1 || true
docker run -d --name edge830 -p 127.0.0.1:18080:80 -p 127.0.0.1:18443:443 \
  -v "$W/site.conf:/etc/nginx/conf.d/site.conf:ro" \
  -v "$W/upstreams.conf:/etc/nginx/conf.d/upstreams.conf:ro" \
  -v "$W/certs:/certs:ro" nginx:stable >/dev/null
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -sk -o /dev/null --resolve "$NAME:18443:127.0.0.1" "https://$NAME:18443/" && break; sleep 0.5
done
docker exec edge830 nginx -t 2>&1 | tail -1

show() { # <label> <url>
  printf '%s\n' "--- $1"
  curl -sk -D - -o /dev/null --resolve "$NAME:18443:127.0.0.1" --resolve "$NAME:18080:127.0.0.1" "$2" \
    | tr -d '\r' | grep -i -E '^(HTTP|x-robots-tag|strict-transport-security|cache-control)' || true
}
show "page (200 from the frontend)"         "https://$NAME:18443/dashboard"
show "static asset (regex location)"        "https://$NAME:18443/_next/static/app.js"
show "API 404 from the backend"             "https://$NAME:18443/api/v1/nope"
show "Stripe webhook path"                  "https://$NAME:18443/webhooks/stripe/webhook"
show "hidden file (nginx's own 403)"        "https://$NAME:18443/.env"
show "plain HTTP (the :80 redirect block)"  "http://$NAME:18080/pricing"
```

Rendered for the staging hostname. Every response is noindex: a page, a static asset, a backend 404, the Stripe webhook path, a 403 that nginx produces itself, and the plain-HTTP redirect. The static asset also carries HSTS now, and exactly one Cache-Control header, the one Next.js set.

```bash
bash /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2d91ea4d-eae7-4965-83d9-6e57760de90d/scratchpad/edge830.sh $PWD dev.sheetpredict.app
```

```output
nginx: configuration file /etc/nginx/nginx.conf test is successful
--- page (200 from the frontend)
HTTP/2 200 
cache-control: public, max-age=31536000, immutable
strict-transport-security: max-age=31536000; includeSubDomains
x-robots-tag: noindex, nofollow
--- static asset (regex location)
HTTP/2 200 
cache-control: public, max-age=31536000, immutable
strict-transport-security: max-age=31536000; includeSubDomains
x-robots-tag: noindex, nofollow
--- API 404 from the backend
HTTP/2 404 
strict-transport-security: max-age=31536000; includeSubDomains
x-robots-tag: noindex, nofollow
--- Stripe webhook path
HTTP/2 404 
strict-transport-security: max-age=31536000; includeSubDomains
x-robots-tag: noindex, nofollow
--- hidden file (nginx's own 403)
HTTP/2 403 
strict-transport-security: max-age=31536000; includeSubDomains
x-robots-tag: noindex, nofollow
--- plain HTTP (the :80 redirect block)
HTTP/1.1 301 Moved Permanently
X-Robots-Tag: noindex, nofollow
```

Rendered for the production hostname, the only difference being `NGINX_SERVER_NAME`. No response carries the header; the security headers are unchanged.

```bash
bash /tmp/claude-1000/-home-frankbria-projects-narrative-modeling-app/2d91ea4d-eae7-4965-83d9-6e57760de90d/scratchpad/edge830.sh $PWD www.sheetpredict.app
```

```output
nginx: configuration file /etc/nginx/nginx.conf test is successful
--- page (200 from the frontend)
HTTP/2 200 
cache-control: public, max-age=31536000, immutable
strict-transport-security: max-age=31536000; includeSubDomains
--- static asset (regex location)
HTTP/2 200 
cache-control: public, max-age=31536000, immutable
strict-transport-security: max-age=31536000; includeSubDomains
--- API 404 from the backend
HTTP/2 404 
strict-transport-security: max-age=31536000; includeSubDomains
--- Stripe webhook path
HTTP/2 404 
strict-transport-security: max-age=31536000; includeSubDomains
--- hidden file (nginx's own 403)
HTTP/2 403 
strict-transport-security: max-age=31536000; includeSubDomains
--- plain HTTP (the :80 redirect block)
HTTP/1.1 301 Moved Permanently
```

The guard fails closed. The same production render answering a hostname that is not on the list (here the apex) is noindex:

```bash
W=$(mktemp -d); mkdir $W/certs; printf 'NGINX_SERVER_NAME=www.sheetpredict.app sheetpredict.app\nNGINX_CERT_DIR=/certs\n' > $W/env; NGINX_CONF_SRC=nginx-staging.conf NGINX_ENV_FILE=$W/env NGINX_TARGET=$W/site.conf NGINX_TEST_CMD=true NGINX_RELOAD_CMD=true bash scripts/deploy/apply_nginx_conf.sh >/dev/null; openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=x -keyout $W/certs/privkey.pem -out $W/certs/fullchain.pem 2>/dev/null; cp $W/certs/fullchain.pem $W/certs/chain.pem; chmod -R a+rX $W; docker run -d --name edge830b -p 127.0.0.1:18443:443 -v $W/site.conf:/etc/nginx/conf.d/site.conf:ro -v $W/certs:/certs:ro nginx:stable >/dev/null; sleep 2; for h in www.sheetpredict.app sheetpredict.app; do printf '%s -> ' $h; curl -sk -D - -o /dev/null --resolve $h:18443:127.0.0.1 https://$h:18443/ | tr -d '\r' | grep -i x-robots-tag || echo '(no X-Robots-Tag)'; done; docker rm -f edge830b >/dev/null; rm -rf $W
```

```output
www.sheetpredict.app -> (no X-Robots-Tag)
sheetpredict.app -> x-robots-tag: noindex, nofollow
```
