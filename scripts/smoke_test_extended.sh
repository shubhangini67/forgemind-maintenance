#!/usr/bin/env bash
# Extended API smoke test — write operations + chat
set -uo pipefail
API="http://127.0.0.1:8000/api/v1"
PASS=0; FAIL=0
ok() { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1 — $2"; FAIL=$((FAIL+1)); }

LOGIN=$(curl -s -X POST "$API/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=engineer@steelplant.com&password=demo1234")
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

echo "=== Extended API Tests ==="

# Chat
code=$(curl -s -o /tmp/chat.json -w "%{http_code}" -X POST "${AUTH[@]}" \
  -d '{"message":"What is the health of BF-001?","equipment_id":1}' "$API/chat")
[[ "$code" == "200" ]] && ok "POST /chat" || bad "POST /chat" "$code"

# Feedback
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${AUTH[@]}" \
  -d '{"source_type":"diagnosis","source_id":1,"rating":"helpful","comment":"test"}' "$API/feedback")
[[ "$code" == "200" || "$code" == "201" ]] && ok "POST /feedback" || bad "POST /feedback" "$code"

# Logbook create
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${AUTH[@]}" \
  -d '{"equipment_id":1,"entry_type":"observation","title":"Smoke test","description":"Automated check"}' "$API/logbook")
[[ "$code" == "200" || "$code" == "201" ]] && ok "POST /logbook" || bad "POST /logbook" "$code"

# Delay log
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${AUTH[@]}" \
  -d '{"equipment_id":1,"delay_hours":2,"reason":"Smoke test","severity":"low"}' "$API/delay-logs")
[[ "$code" == "200" || "$code" == "201" ]] && ok "POST /delay-logs" || bad "POST /delay-logs" "$code"

# Report generate
code=$(curl -s -o /tmp/report.json -w "%{http_code}" -X POST "${AUTH[@]}" \
  -d '{"report_type":"priority","equipment_id":1,"title":"Smoke Test Report"}' "$API/reports/generate")
[[ "$code" == "200" ]] && ok "POST /reports/generate" || bad "POST /reports/generate" "$code"

# PDF types
for rt in diagnosis scenario decision priority executive; do
  code=$(curl -s -o /tmp/t.pdf -w "%{http_code}" -X POST "${AUTH[@]}" \
    -d "{\"report_type\":\"$rt\",\"equipment_id\":1,\"payload\":{\"equipment_code\":\"BF-001\",\"tasks\":[]}}" "$API/reports/pdf/export")
  if [[ "$code" == "200" ]] && [[ "$(head -c 4 /tmp/t.pdf)" == "%PDF" ]]; then ok "PDF $rt"; else bad "PDF $rt" "$code"; fi
done

# Alert lifecycle (get first open alert)
ALERT_ID=$(curl -s "${AUTH[@]}" "$API/alerts?status=open&limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
if [[ -n "$ALERT_ID" ]]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH -H "Authorization: Bearer $TOKEN" "$API/alerts/$ALERT_ID/acknowledge")
  [[ "$code" == "200" ]] && ok "PATCH alert acknowledge" || bad "PATCH alert acknowledge" "$code"
else
  echo "  ~ alert ack (no open alerts)"
fi

# Scheduler reminder create
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${AUTH[@]}" \
  -d '{"equipment_id":1,"title":"Smoke reminder","due_date":"2026-06-20","priority":"medium"}' "$API/scheduler/reminders")
[[ "$code" == "200" || "$code" == "201" ]] && ok "POST scheduler reminder" || bad "POST scheduler reminder" "$code"

# Simulate decision immediate failure
code=$(curl -s -o /tmp/dec.json -w "%{http_code}" -X POST "${AUTH[@]}" \
  -d '{"equipment_id":1,"mode":"immediate_failure"}' "$API/simulate/decision")
[[ "$code" == "200" ]] && python3 -c "import json; d=json.load(open('/tmp/dec.json')); assert d.get('recommendation')" && ok "POST decision immediate failure" || bad "POST decision immediate failure" "$code"

# Documents content
DOC_ID=$(curl -s "${AUTH[@]}" "$API/documents" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
if [[ -n "$DOC_ID" ]]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$API/documents/$DOC_ID/content")
  [[ "$code" == "200" ]] && ok "GET document content" || bad "GET document content" "$code"
fi

echo "=== Extended: $PASS passed, $FAIL failed ==="
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
