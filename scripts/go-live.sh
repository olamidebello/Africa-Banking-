#!/usr/bin/env bash
set -euo pipefail
cd /opt/africa-bankh
if [ "$(id -u)" -ne 0 ]; then
  echo 'Run this deployment command as root on the Olamidepanel server.' >&2
  exit 1
fi
git pull --ff-only origin main
python3 -m unittest discover -s tests -v
ansible-playbook -i localhost, -c local ansible/deploy.yml --syntax-check
ansible-playbook -i localhost, -c local ansible/deploy.yml -e bankh_tls_email=dobcalldemo@gmail.com
printf '\nPublic sandbox deployment checks passed. Sign in at https://banking.africandroid.world/\n'
printf 'If no administrator exists, run: python3 scripts/create-admin.py\n'
