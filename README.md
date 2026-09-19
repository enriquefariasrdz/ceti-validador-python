# CETI Certificate Validator

Certificate validation application for CETI English.

## Current public endpoint

- Validator: `https://validar.cetienglish.com`
- Main CETI website remains hosted separately on Wix at `cetienglish.com`.
- DNS for `validar.cetienglish.com` is an A record managed in Wix DNS and points to the Hetzner server.
- HTTPS is terminated by Coolify's Traefik proxy using Let's Encrypt.

## Application architecture

```text
Visitor
  |
  v
validar.cetienglish.com
  |
  v
Wix DNS
  |
  v
Hetzner server
  |
  v
Coolify / Traefik
  |
  v
Flask CETI validator
  |
  +--> Vault (database credentials)
  |
  +--> MariaDB (certificate records)
```

The application is deployed from this GitHub repository through Coolify.

## Infrastructure checkpoint

The currently tested setup includes:

- Flask certificate validator deployed through Coolify.
- Public custom domain `https://validar.cetienglish.com`.
- Valid Let's Encrypt HTTPS certificate.
- Functional certificate lookup tested with the development record `CETI-TR-2026-G2401`.
- MariaDB stores certificate information.
- HashiCorp Vault provides database credentials to the application.
- Vault automatically unseals after a Hetzner reboot using a systemd service and local unseal script.
- Ubuntu nginx is disabled because Coolify/Traefik owns ports 80 and 443.
- Full server reboot was tested successfully after fixing the nginx/Traefik port conflict.
- Daily verified MariaDB backups are stored locally and copied off-server to Google Drive using rclone.

## Backups

See [`docs/BACKUPS.md`](docs/BACKUPS.md) for the complete backup and rclone configuration, verification procedure, cron schedule, and reconstruction instructions.

Important: PDFs are **not** intended to be preserved or archived as part of the current CETI design. The goal is to keep the validator lightweight and present certificate information attractively from structured database records.

## Important server-side paths

These files live on the Hetzner server and are intentionally documented here rather than committed with live secrets:

- Vault auto-unseal script: `/root/ceti-vault/unseal.sh`
- Vault unseal key file: `/root/ceti-vault/unseal-keys` (**secret; never commit**)
- Vault systemd unit: `/etc/systemd/system/ceti-vault-unseal.service`
- Database backup directory: `/root/ceti-backups`
- Database backup script: `/root/ceti-backups/backup-db.sh`
- Database backup log: `/root/ceti-backups/backup.log`

## Secrets policy

Do not commit live credentials to this repository. In particular, never commit:

- Vault unseal keys
- Vault AppRole credentials
- MariaDB passwords
- Coolify API tokens
- rclone OAuth access or refresh tokens
- Google OAuth secrets
- application administrator passwords
- `.env` files containing credentials

Documentation should contain the names, locations, architecture, commands, and reconstruction procedure while secret values remain outside Git.

## Documentation rule

Infrastructure changes are part of the project. When the deployment architecture, Vault setup, database configuration, backup process, DNS/domain configuration, or operational procedure changes, update the corresponding documentation in this repository as part of the same work.
