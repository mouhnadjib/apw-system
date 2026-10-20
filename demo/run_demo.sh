#!/usr/bin/env bash
# يشغّل خادم العرض التجريبي (بيانات وهمية، SQLite، مفاتيح مؤقتة) على macOS/Linux.
#   ./demo/run_demo.sh            تشغيل (يعبّئ البيانات عند أول مرة)
#   ./demo/run_demo.sh --reset    حذف بيانات العرض وإعادة تعبئتها
# يستمع على كل واجهات الشبكة المحلية كي يصل إليه الهاتف: لا تشغّله على شبكة غير موثوقة.
set -euo pipefail
cd "$(dirname "$0")/.."
D="$PWD/demo"
mkdir -p "$D/data"

if [ ! -d "$D/venv" ]; then
  python3 -m venv "$D/venv"
  "$D/venv/bin/pip" install -q --upgrade pip
  "$D/venv/bin/pip" install -q -r requirements.txt
fi
PY="$D/venv/bin/python"

# مفاتيح تجريبية تُولَّد مرة واحدة (لا علاقة لها بمفاتيح الخادم الحقيقي)
if [ ! -f "$D/demo.env" ]; then
  "$PY" -m app.cli gen-keys > "$D/demo.env"
fi
set -a
# shellcheck disable=SC1091
. "$D/demo.env"
set +a
export APW_DATABASE_URL="sqlite:///$D/demo.db"
export APW_DATA_DIR="$D/data"
export APW_FCM_CREDENTIALS=""

"$PY" -m demo.seed "$@"

# عنوان الحاسوب على الشبكة المحلية
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)"
echo
echo "عنوان الخادم للتطبيق:  http://${IP:-<عنوان-الحاسوب>}:8000"
echo "لوحة الديوان:           http://localhost:8000/panel/"
echo
exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
