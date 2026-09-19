# CETI Vault Backups

This document records the verified backup and disaster-recovery design for the production HashiCorp Vault used by the CETI certificate validator. No secret values are stored here.

## Production Vault

The CETI validator uses:

```text
vault-mh5tyoqpbcpcv1usplkjmamg
```

Storage backend: `file`

Container data path: `/vault/file`

Persistent Docker volume:

```text
/var/lib/docker/volumes/mh5tyoqpbcpcv1usplkjmamg_vault-data/_data
```

The production volume was approximately 528 KB when the backup procedure was established.

## Critical operational rule: Docker health is not Vault readiness

On 2026-09-19 an application-level certificate lookup returned HTTP 500 even though the production Vault Docker container reported `running` and `healthy` and the validator homepage returned HTTP 200.

Application logs showed the failure occurred during AppRole login, where Vault returned HTTP 503. Direct inspection of `/v1/sys/health` established the real state:

```text
initialized: true
sealed: true
```

The cause was the original backup procedure: it stopped Vault to obtain a consistent file-backend backup and restarted the container afterward, but treated Docker `healthy` as sufficient. A Shamir-sealed Vault restarts in a sealed state, so Docker container health alone did not prove that AppRole or secret access was operational.

The production Vault was unsealed using protected recovery material. Afterward it reported:

```text
Initialized: True
Sealed: False
Standby: False
```

Certificate lookup for the known validation record succeeded again.

Operational rule: **never use Docker health alone as the readiness test for CETI Vault.** A successful production check must confirm `initialized=true` and `sealed=false` through the Vault API. Application-level certificate validation should also be tested after maintenance that restarts Vault.

## Corrected production backup procedure

`/root/ceti-backups/backup-vault.sh` was corrected after the incident. The current procedure:

1. Confirms the production Vault container and data directory exist.
2. Confirms protected unseal material is readable.
3. Refuses to begin if production Vault is already sealed or unavailable.
4. Stops Vault for a consistent backup of the `file` storage backend.
5. Creates a gzip tar archive with numeric ownership preserved.
6. Restarts the production Vault container.
7. Waits for the Vault API itself, rather than relying only on Docker health.
8. Detects the expected sealed state after restart.
9. Supplies protected unseal shares without printing their values.
10. Verifies `initialized=true` and `sealed=false` before proceeding.
11. Verifies gzip integrity.
12. Verifies that `./core/` and `./logical/` exist in the archive.
13. Finalizes the local archive with mode `600`.
14. Uploads it to Google Drive.
15. Runs `rclone check --one-way` against the remote copy.
16. Performs another final Vault API check requiring `sealed=false`.
17. Removes generated local production Vault archives older than 30 days.
18. Reports `CETI VAULT BACKUP COMPLETE` only after all required checks succeed.

The script also contains emergency recovery handling so an interruption while Vault is stopped attempts to start and unseal Vault rather than merely restarting the container.

## Verified corrected backup test — 2026-09-19

Before another production restart, the corrected archive-validation logic was tested independently against a temporary archive. It passed:

```text
GZIP VERIFIED
CORE DATA VERIFIED
LOGICAL DATA VERIFIED
ARCHIVE VALIDATION TEST PASSED
```

Production Vault remained initialized, unsealed, and active throughout that validation-only test.

The complete corrected backup procedure was then run against production. It successfully restarted and automatically unsealed Vault, produced the following new backup:

```text
/root/ceti-backups/ceti-vault-2026-09-19_05-29-23.tar.gz
```

The archive was approximately 39 KB locally (39,719 bytes remotely) and was uploaded to:

```text
ceti-google-drive:CETI-Backups/Vault/
```

Post-backup verification confirmed:

```text
Initialized: True
Sealed: False
Standby: False
Version: 2.1.1
Docker Status: running
Docker Health: healthy
Validator homepage: HTTP 200
```

Most importantly, an application-level lookup of `CETI-TR-2026-G2401` succeeded after the backup. This exercises the production application path through Vault/AppRole and MariaDB rather than relying only on the homepage health response.

The corrected backup procedure is therefore operationally verified end-to-end.

## Legacy Vault retirement state

An older Vault instance exists:

```text
vault-r4ukak9jk6z6tfms22amldjs
```

Investigation established that the current CETI validator points to the newer production Vault. The legacy Vault had its own independent file-storage volume:

```text
/var/lib/docker/volumes/r4ukak9jk6z6tfms22amldjs_vault-data/_data
```

Its data volume was approximately 436 KB. Before retirement it was stopped cleanly and a final archive was created:

```text
/root/ceti-backups/ceti-vault-legacy-r4ukak9-2026-09-19.tar.gz
```

The archive was approximately 24 KB compressed, passed `gzip -t`, contained Vault `core/` data, and was uploaded to:

```text
ceti-google-drive:CETI-Backups/Vault-Legacy/
```

`rclone check --one-way` reported zero differences and one matching file. The legacy Vault remains intentionally stopped rather than deleted. Its container and Docker volume should remain intact during an observation period until retirement is explicitly approved.

The 2026-09-19 sealed-state incident was confirmed to involve the newer production Vault, not a dependency on the legacy Vault.

## Backup locations

Local backup directory:

```text
/root/ceti-backups
```

Production backup script:

```text
/root/ceti-backups/backup-vault.sh
```

Backup log:

```text
/root/ceti-backups/vault-backup.log
```

Production Google Drive destination:

```text
ceti-google-drive:CETI-Backups/Vault/
```

Legacy archival destination:

```text
ceti-google-drive:CETI-Backups/Vault-Legacy/
```

Production archive naming convention:

```text
ceti-vault-YYYY-MM-DD_HH-MM-SS.tar.gz
```

Local generated production Vault backups older than 30 days are removed after a successful backup cycle.

## Schedule

Vault backups run weekly on Sunday at 04:00 server time:

```cron
0 4 * * 0 /root/ceti-backups/backup-vault.sh >> /root/ceti-backups/vault-backup.log 2>&1
```

MariaDB backups run daily at 03:00:

```cron
0 3 * * * /root/ceti-backups/backup-db.sh >> /root/ceti-backups/backup.log 2>&1
```

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

Existing protected unseal material was supplied directly from the server-side recovery file without printing key values. The restored Vault successfully became unsealed. Its logs confirmed successful post-unseal setup and restoration of the CETI KV secret engine and AppRole authentication backend.

### Phase 4 — application authentication and secret-access validation

Historical AppRole files on the server did not match the credentials currently deployed to the CETI application. This was identified without printing either credential. Current production AppRole credentials were separately protected in 1Password under `CETI Infrastructure`.

Using current credentials directly from the running CETI application container, the isolated restored Vault successfully authenticated through AppRole:

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

This verifies:

```text
verified backup
    -> isolated extraction
    -> restored Vault boot
    -> existing unseal material
    -> current CETI AppRole authentication
    -> application secret path accessible
```

The temporary restore environment was removed after testing and production Vault remained healthy.

## Earlier recovery archives

Three earlier recovery archives were copied to the production Google Drive Vault backup directory and verified with `rclone check`:

```text
vault-current-sealed-20260916-112857.tar.gz
vault-data-backup-20260916-100009.tar.gz
vault-recovery-verified-20260916-114849.tar.gz
```

Verification reported zero differences and three matching files. Local server permissions were tightened to mode `600`.

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

Check the real Vault state:

```bash
docker exec vault-mh5tyoqpbcpcv1usplkjmamg wget -qO- http://127.0.0.1:8200/v1/sys/health
```

A production-ready state requires at least `initialized=true` and `sealed=false`.

List local production Vault backups:

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

Confirm the legacy Vault remains stopped during its observation period:

```bash
docker inspect vault-r4ukak9jk6z6tfms22amldjs --format 'Status={{.State.Status}}'
```

After Vault maintenance or backup testing, verify a real certificate lookup such as `CETI-TR-2026-G2401`; a homepage HTTP 200 alone is not a sufficient application health check.

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
11. Verify a real certificate lookup before returning the service to normal operation.

The 2026-09-19 restore drill and subsequent corrected production backup test validated both recovery and normal post-backup operation.
