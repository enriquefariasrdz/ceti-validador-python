# CETI Vault Backups

This document records the verified backup and disaster-recovery design for the production HashiCorp Vault used by the CETI certificate validator. No secret values are stored here.

## Production Vault

The CETI validator uses:

```text
vault-mh5tyoqpbcpcv1usplkjmamg
```

Storage backend: `file`

Container data path: `/vault/file`

Persistent Docker volume on the Hetzner host:

```text
/var/lib/docker/volumes/mh5tyoqpbcpcv1usplkjmamg_vault-data/_data
```

The production volume was approximately 528 KB when the backup procedure was established.

## Legacy Vault retirement state

An older Vault instance also existed:

```text
vault-r4ukak9jk6z6tfms22amldjs
```

Investigation on 2026-09-19 established that no other running container referenced this legacy Vault hostname. The current CETI validator uses the newer production Vault listed above.

The legacy Vault had its own independent file-storage volume:

```text
/var/lib/docker/volumes/r4ukak9jk6z6tfms22amldjs_vault-data/_data
```

Its data volume was approximately 436 KB.

Before retirement, the legacy Vault was stopped cleanly and a final archive was created:

```text
/root/ceti-backups/ceti-vault-legacy-r4ukak9-2026-09-19.tar.gz
```

The archive was approximately 24 KB compressed, passed `gzip -t`, and contained Vault `core/` data. It was uploaded to the separate Google Drive archival location:

```text
ceti-google-drive:CETI-Backups/Vault-Legacy/
```

Remote verification with `rclone check --one-way` reported zero differences and one matching file. The legacy Vault was intentionally left stopped (`Status=exited`) rather than deleted. Its container and Docker volume should remain intact during an observation period and must not be removed until production operation has been reconfirmed and retirement is explicitly approved.

## Why the production backup briefly stops Vault

The production Vault uses the `file` storage backend rather than integrated Raft storage. Therefore `vault operator raft snapshot` is not the applicable backup mechanism.

For a consistent filesystem archive, the backup procedure briefly stops the production Vault container, archives the persistent file-storage volume, explicitly starts Vault again, waits for the container health check to return healthy, verifies the archive, uploads it to Google Drive, and verifies the remote copy.

The container restart policy is `unless-stopped`, so the backup script explicitly restarts Vault after the archive step. The script also includes an EXIT cleanup trap that attempts an emergency restart if execution is interrupted while Vault is stopped.

## Backup locations

Local backup directory: `/root/ceti-backups`

Backup script: `/root/ceti-backups/backup-vault.sh`

Backup log: `/root/ceti-backups/vault-backup.log`

Production Google Drive destination:

```text
ceti-google-drive:CETI-Backups/Vault/
```

Legacy archival destination:

```text
ceti-google-drive:CETI-Backups/Vault-Legacy/
```

Local generated archive naming convention:

```text
ceti-vault-YYYY-MM-DD_HH-MM-SS.tar.gz
```

Local generated production Vault backups older than 30 days are removed by the backup script after a successful backup cycle.

## Schedule

Vault backups run weekly on Sunday at 04:00 server time:

```cron
0 4 * * 0 /root/ceti-backups/backup-vault.sh >> /root/ceti-backups/vault-backup.log 2>&1
```

MariaDB backups run daily at 03:00:

```cron
0 3 * * * /root/ceti-backups/backup-db.sh >> /root/ceti-backups/backup.log 2>&1
```

## Verified backup flow

1. Confirm the production Vault container exists.
2. Confirm the production Vault data directory exists.
3. Stop the production Vault container.
4. Create a gzip-compressed tar archive of the persistent Vault data with numeric ownership preserved.
5. Explicitly restart Vault.
6. Wait for Docker health status to become `healthy`.
7. Run `gzip -t` against the local archive.
8. Confirm the archive contains Vault `core/` and `logical/` data.
9. Move the verified temporary archive into its final local filename and restrict it to mode `600`.
10. Upload the archive to `CETI-Backups/Vault/` in Google Drive.
11. Run `rclone check --one-way` to compare the local archive with the remote copy.
12. Delete generated local production Vault backups older than 30 days.

## First verified automated-backup test

The backup script was manually tested before being added to cron. The test successfully stopped production Vault, created the archive, restarted Vault, returned Vault to healthy status, verified the local archive, uploaded it to Google Drive, and completed `rclone check` with zero differences and one matching file.

The first generated automated archive was approximately 40 KB compressed.

## Verified disaster-recovery drill — 2026-09-19

A complete non-production restore drill was performed using:

```text
/root/ceti-backups/ceti-vault-2026-09-19_04-55-50.tar.gz
```

Production Vault and its Docker volume were not modified during the drill.

### Phase 1 — archive restoration

The archive passed `gzip -t`, was extracted into an isolated restore directory, and restored approximately 528 KB of Vault data. The restored filesystem contained `core/`, `logical/`, `sys/`, and `auth/`.

### Phase 2 — isolated Vault boot

An isolated test Vault was started against the restored data and bound only to localhost on port `18200`. It reported initialized=true and sealed=true, demonstrating that the filesystem backup booted as the previously initialized Vault rather than as a new/empty Vault.

### Phase 3 — recovery-key validation

The existing protected unseal material was supplied directly from the server-side recovery file without printing key values. The restored Vault successfully became unsealed. Its logs confirmed successful post-unseal setup and restoration of the CETI KV secret engine and AppRole authentication backend.

### Phase 4 — application authentication and secret-access validation

Historical AppRole files on the server did not match the credentials currently deployed to the CETI application. This was identified without printing either credential. Current production AppRole credentials were separately protected in 1Password under `CETI Infrastructure`.

Using the current credentials directly from the running CETI application container, the isolated restored Vault successfully authenticated through AppRole:

```text
APPROLE LOGIN: OK
```

The authenticated test accessed:

```text
ceti/data/ceti-validador
```

Result:

```text
CETI SECRET PATH: ACCESSIBLE
Secret fields present: 3
Secret values displayed: NO
```

This verifies the complete recovery chain:

```text
verified backup
    -> isolated extraction
    -> restored Vault boot
    -> existing unseal material
    -> current CETI AppRole authentication
    -> application secret path accessible
```

The temporary restore container and restore directory were removed after testing. Production Vault was reconfirmed as `running` and `healthy` afterward.

## Earlier recovery archives

Three earlier Vault recovery archives were copied to the production Google Drive Vault backup directory and verified together with `rclone check`:

```text
vault-current-sealed-20260916-112857.tar.gz
vault-data-backup-20260916-100009.tar.gz
vault-recovery-verified-20260916-114849.tar.gz
```

Verification reported zero differences and three matching files. Their local server permissions were tightened from mode `644` to `600`.

## Secret recovery layers

Vault data archives are stored off-server in Google Drive. Human recovery/bootstrap material is separately protected in the dedicated 1Password vault named `CETI Infrastructure`.

Current application AppRole credentials have dedicated recovery copies in 1Password. Older AppRole recovery artifacts must be treated as historical/stale unless independently verified against the current deployment.

Secret values must never be committed to GitHub.

See `docs/SECRETS-AND-RECOVERY.md` for the secrets architecture and `docs/BACKUPS.md` for MariaDB/rclone backup details.

## Operational checks

Run a production Vault backup manually:

```bash
/root/ceti-backups/backup-vault.sh
```

Review the scheduled backup log:

```bash
tail -100 /root/ceti-backups/vault-backup.log
```

List generated local production Vault backups:

```bash
ls -lh /root/ceti-backups/ceti-vault-*.tar.gz
```

List off-server production Vault backups:

```bash
rclone lsl ceti-google-drive:CETI-Backups/Vault/
```

List the archived legacy Vault backup:

```bash
rclone lsl ceti-google-drive:CETI-Backups/Vault-Legacy/
```

Confirm production Vault health:

```bash
docker inspect vault-mh5tyoqpbcpcv1usplkjmamg --format 'Status={{.State.Status}} Health={{.State.Health.Status}}'
```

Confirm the legacy Vault remains stopped during its observation period:

```bash
docker inspect vault-r4ukak9jk6z6tfms22amldjs --format 'Status={{.State.Status}}'
```

## Restore procedure summary

Do not overwrite a running Vault data directory. A production restore must be treated as a controlled disaster-recovery operation:

1. Select and locally verify the intended Vault archive.
2. Stop the target/replacement Vault before modifying its data directory.
3. Preserve any existing target data before replacement.
4. Extract the archive while preserving numeric ownership and permissions.
5. Start Vault using the same `file` storage configuration.
6. Confirm it reports initialized and sealed.
7. Supply protected unseal material without exposing it in logs/history.
8. Confirm Vault becomes unsealed and completes post-unseal setup.
9. Authenticate using current application AppRole credentials from the protected recovery source.
10. Verify access to `ceti/data/ceti-validador` without printing secret values.
11. Verify the CETI application can authenticate and operate normally before returning the service to production.

The 2026-09-19 isolated restore drill successfully validated this recovery chain through application secret access.
