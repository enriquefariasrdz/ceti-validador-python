# CETI Vault Backups

This document records the verified backup design for the production HashiCorp Vault used by the CETI certificate validator. No secret values are stored here.

## Production Vault

The CETI validator is configured to use the production Vault container:

```text
vault-mh5tyoqpbcpcv1usplkjmamg
```

Vault storage backend:

```text
file
```

Vault data path inside the container:

```text
/vault/file
```

Persistent Docker volume on the Hetzner host:

```text
/var/lib/docker/volumes/mh5tyoqpbcpcv1usplkjmamg_vault-data/_data
```

The production volume was approximately 528 KB when the backup procedure was established.

A second older Vault container exists on the host but is not currently used by the CETI validator. It must not be deleted until its purpose/history has been separately reviewed.

## Why the backup briefly stops Vault

The production Vault uses the `file` storage backend rather than integrated Raft storage. Therefore `vault operator raft snapshot` is not the applicable backup mechanism.

For a consistent filesystem archive, the backup procedure briefly stops the production Vault container, archives the persistent file-storage volume, explicitly starts Vault again, waits for the container health check to return healthy, verifies the archive, uploads it to Google Drive, and verifies the remote copy.

The container restart policy is `unless-stopped`, so the backup script explicitly restarts Vault after the archive step. The script also includes an EXIT cleanup trap that attempts an emergency restart if execution is interrupted while Vault is stopped.

## Backup locations

Local backup directory:

```text
/root/ceti-backups
```

Backup script:

```text
/root/ceti-backups/backup-vault.sh
```

Backup log:

```text
/root/ceti-backups/vault-backup.log
```

Google Drive destination through rclone:

```text
ceti-google-drive:CETI-Backups/Vault/
```

Local generated archive naming convention:

```text
ceti-vault-YYYY-MM-DD_HH-MM-SS.tar.gz
```

Local generated Vault backups older than 30 days are removed by the backup script after a successful backup cycle.

## Schedule

Vault backups run weekly on Sunday at 04:00 server time:

```cron
0 4 * * 0 /root/ceti-backups/backup-vault.sh >> /root/ceti-backups/vault-backup.log 2>&1
```

The MariaDB backup remains separate and runs daily at 03:00:

```cron
0 3 * * * /root/ceti-backups/backup-db.sh >> /root/ceti-backups/backup.log 2>&1
```

## Verified backup flow

The Vault backup performs the following sequence:

1. Confirm the production Vault container exists.
2. Confirm the production Vault data directory exists.
3. Stop the production Vault container.
4. Create a gzip-compressed tar archive of the persistent Vault data with numeric ownership preserved.
5. Explicitly restart Vault.
6. Wait for the Docker health status to become `healthy`.
7. Run `gzip -t` against the local archive.
8. Confirm the archive contains Vault `core/` and `logical/` data.
9. Move the verified temporary archive into its final local filename and restrict it to mode `600`.
10. Upload the archive to `CETI-Backups/Vault/` in Google Drive.
11. Run `rclone check --one-way` to compare the local archive with the remote copy.
12. Delete generated local Vault backups older than 30 days.

## First verified automated-backup test

The backup script was manually tested before being added to cron. The test successfully:

- stopped production Vault;
- created the archive;
- restarted Vault;
- returned Vault to healthy status;
- verified the local archive;
- uploaded the archive to Google Drive; and
- completed `rclone check` with zero differences and one matching file.

The first generated automated archive was approximately 40 KB compressed.

## Earlier recovery archives

Three earlier Vault recovery archives were also copied to the separate Google Drive Vault backup directory and verified together with `rclone check`:

```text
vault-current-sealed-20260916-112857.tar.gz
vault-data-backup-20260916-100009.tar.gz
vault-recovery-verified-20260916-114849.tar.gz
```

Verification reported zero differences and three matching files. Their local server permissions were tightened from mode `644` to `600`.

## Secret recovery layers

Vault data archives are stored off-server in Google Drive. Human recovery/bootstrap material is separately protected in the dedicated 1Password vault named `CETI Infrastructure`.

Examples of protected recovery items include the Vault unseal material and AppRole recovery information. Secret values must never be committed to GitHub.

See `docs/SECRETS-AND-RECOVERY.md` for the secrets architecture and `docs/BACKUPS.md` for MariaDB/rclone backup details.

## Operational checks

Run a Vault backup manually:

```bash
/root/ceti-backups/backup-vault.sh
```

Review the scheduled backup log:

```bash
tail -100 /root/ceti-backups/vault-backup.log
```

List generated local Vault backups:

```bash
ls -lh /root/ceti-backups/ceti-vault-*.tar.gz
```

List off-server Vault backups:

```bash
rclone lsl ceti-google-drive:CETI-Backups/Vault/
```

Confirm production Vault container health:

```bash
docker inspect vault-mh5tyoqpbcpcv1usplkjmamg --format '{{.State.Health.Status}}'
```

## Restore caution

Do not overwrite a running Vault data directory. A restore should be treated as a controlled disaster-recovery operation: stop the target Vault, preserve the current data directory before replacement, restore the selected archive while preserving ownership/permissions, start Vault, unseal it if necessary, and verify application authentication and secret access before returning the service to production.

A full restore drill should be performed separately on a non-production/test Vault before treating the recovery procedure as fully proven.
