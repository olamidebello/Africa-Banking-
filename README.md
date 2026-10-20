# Africa Bank
Your ambition. Our continent.

Initial development sandbox for banking.africandroid.world. Original Africa Bank branding; independent of Citi and Field Nation.

## Run
Python 3.11+. Set BANKH_ADMIN_EMAIL and BANKH_ADMIN_PASSWORD (at least 12 characters recommended) in the process environment before the initial start. Run `python3 app.py`; open http://127.0.0.1:18840. No hard-coded credentials. Database files and secrets are ignored by Git.

## Implemented
Responsive public site; customer registration/login/logout; salted PBKDF2 passwords; expiring HttpOnly sessions; tenant-scoped account and request queries; zero-funded USD demo accounts; internal transfer requests with atomic paired ledger entries and independent approval; card, loan, business, support requests; operations queue; superadmin tenant creation; audit records; draft legal pages; installable web manifest; generated original brand assets.

## Deployment
On Olamidepanel server: `ansible-playbook -i localhost, -c local ansible/deploy.yml -e bankh_tls_email=YOUR_EMAIL`.
DNS A for banking.africandroid.world must resolve to that server before TLS issuance. Playbook pulls main into /opt/africa-bankh and runs dedicated systemd service on loopback 18840. It refuses jobs.africandroid.world to preserve Africa Jobs. Configure admin bootstrap in protected /etc/africa-bankh.env, restart once, then remove bootstrap password. Never commit that file. Existing nginx host files are preserved to avoid erasing certbot configuration.

## Honest scope / next work
Not an operating bank. No real deposits, external transfers, card issuance, credit decisions, investments, rewards, wire/Zelle rails, KYC providers, recovery emails, MFA, or regulated disclosures are connected. No claims of deposit insurance. No funding endpoint exists. Demo accounts start at zero; ledger tests use isolated fixtures. Legal text is draft and requires operator details before live use.

Tenant database and isolation exist, but tenant user provisioning, tenant administrator assignment, domain branding and invitation flows remain to implement. Superadmin sees its own tenant’s operations and the tenant registry. There is no arbitrary balance editing.

The mobile deliverable currently is an installable web app, not an APK. Native Android packaging/signing and africanappsstore.space publication are pending. No fake download link is shown. Android should use the same HTTPS site after deployment and must not bypass certificate validation.

Production hardening still requires a production WSGI/ASGI server, authentication throttling, MFA, recovery, security review, monitoring/backups, provider integrations and reconciliation. The standard-library HTTP server is for initial sandbox evaluation only. Do not expose this build as a live financial service.

Logo prompt: original emerald/gold Africa continent integrated with a bank arch; exact name Africa Bank; slogan Your ambition. Our continent. Generated using built-in image generation. Same artwork used in header, card background and app icons.

## Afira (proposed currency)
Name: Afira. Symbol: Ⱥ. Proposed code: AFR. Pronunciation: Ah-FEE-rah. Subdivision: 1 Afira = 100 cents. Examples: Ⱥ10 · Ⱥ250 · Ⱥ1,000. The name combines Africa and a new era, representing shared prosperity across the continent; the strong A symbol connects it to Africa. Available for new sandbox accounts alongside USD; balances use integer cents and explicit Ⱥ formatting. Transfers require matching currencies; there is no exchange rate or automatic conversion. This is a platform-defined proposed currency, not a claim of official currency status. Existing accounts retain their currency.

## Pull and deploy on the server
```bash
apt-get update
apt-get install -y git ansible
git clone https://github.com/olamidebello/Africa-Banking-.git /opt/africa-bankh
cd /opt/africa-bankh
ansible-playbook -i localhost, -c local ansible/deploy.yml -e bankh_tls_email=dobcalldemo@gmail.com
```
For later updates, run the same playbook from /opt/africa-bankh. It pulls main automatically, preserves the database and environment file, restarts the service, validates nginx, and verifies backend and HTTPS health. DNS must point banking.africandroid.world at the server before running TLS provisioning. From an authorized workstation use `ansible-playbook -i ansible/inventory.ini ansible/deploy.yml -e bankh_tls_email=dobcalldemo@gmail.com` with your configured SSH key.
