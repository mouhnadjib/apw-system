#!/usr/bin/env bash
# نسخة احتياطية مشفّرة (قاعدة البيانات + الملفات). شغّله يومياً عبر cron.
# يتطلب ملف عبارة المرور: /root/.apw-backup-pass  (chmod 600)
set -euo pipefail
cd "$(dirname "$0")"
DEST="${1:-/mnt/backup}"          # قرص منفصل أو مسار شبكي
STAMP=$(date +%Y%m%d-%H%M)
mkdir -p "$DEST"
{
  docker compose exec -T db pg_dump -U apw apw
} | gpg --batch --symmetric --cipher-algo AES256 --passphrase-file /root/.apw-backup-pass \
    -o "$DEST/db-$STAMP.sql.gpg"
tar -C /srv/apw -cf - data | gpg --batch --symmetric --cipher-algo AES256 \
    --passphrase-file /root/.apw-backup-pass -o "$DEST/files-$STAMP.tar.gpg"
# الاحتفاظ بآخر 30 نسخة
ls -1t "$DEST"/db-*.gpg | tail -n +31 | xargs -r rm --
ls -1t "$DEST"/files-*.gpg | tail -n +31 | xargs -r rm --
