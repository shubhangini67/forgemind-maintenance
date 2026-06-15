#!/usr/bin/env bash
# Smoke test — backend API endpoints (requires running backend on :8000)
set -uo pipefail

API="http://127.0.0.1:8000/api/v1"
PASS=0
FAIL=0
SKIP=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ✗ $1 — $2"; FAIL=$((FAIL+1)); }
skip() { echo "  ~ $1 (skipped: $2)"; SKIP=$((SKIP+1)); }

check() {
  local name="$1" method="$2" path="$3" expect="${4:-200}" body="${5:-}"
  local args=(-s -o /tmp/smoke_body -w "%{http_code}" -X "$method")
  [[ -n "$TOKEN" ]] && args+=(-H "Authorization: Bearer $TOKEN")
  [[ -n "$body" ]] && args+=(-H "Content-Type: application/json" -d "$body")
  code=$(curl "${args[@]}" "$API$path" 2>/dev/null || echo "000")
  if [[ "$code" == "$expect" ]]; then ok "$name ($code)"; else bad "$name" "HTTP $code (expected $expect)"; fi
}

check_pdf() {
  local name="$1" body="$2"
  code=$(curl -s -o /tmp/smoke.pdf -w "%{http_code}" -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "$body" "$API/reports/pdf/export" 2>/dev/null || echo "000")
  if [[ "$code" == "200" ]] && [[ -s /tmp/smoke.pdf ]]; then
    head=$(head -c 4 /tmp/smoke.pdf)
    if [[ "$head" == "%PDF" ]]; then ok "$name (PDF $code)"; else bad "$name" "not a PDF"; fi
  else
    bad "$name" "HTTP $code"
  fi
}

echo "=== SteelPlant Maintenance Wizard — API Smoke Test ==="
echo ""

# Health (no auth)
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)
if [[ "$code" == "200" ]]; then ok "Backend health"; else bad "Backend health" "HTTP $code"; fi

# Login
LOGIN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=engineer@steelplant.com&password=demo1234" 2>/dev/null)
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [[ -n "$TOKEN" ]]; then ok "Auth login"; else bad "Auth login" "no token"; fi

echo ""
echo "--- Equipment & Dashboard ---"
check "GET /equipment" GET "/equipment"
check "GET /dashboard" GET "/equipment/dashboard"
check "GET /plant-twin" GET "/equipment/plant-twin"
check "GET /priority" GET "/equipment/priority"
check "GET /equipment/1" GET "/equipment/1"
check "GET /equipment/1/sensors" GET "/equipment/1/sensors"
check "GET /equipment/1/predictions" GET "/equipment/1/predictions"
check "GET /equipment/1/health" GET "/equipment/1/health"

echo ""
echo "--- Monitor & Alerts ---"
check "GET monitor live" GET "/monitor/live/1"
check "GET alerts" GET "/alerts"
check "GET alerts summary" GET "/alerts/summary"

echo ""
echo "--- AI & Diagnosis ---"
check "GET chat conversations" GET "/chat/conversations"
check "POST diagnose" POST "/diagnose" 200 '{"equipment_id":1,"symptoms":"high vibration bearing noise","operating_conditions":"normal load"}'
check "GET feedback stats" GET "/feedback/stats"

echo ""
echo "--- Simulator ---"
check "GET simulate dependencies" GET "/simulate/dependencies"
check "POST simulate failure" POST "/simulate" 200 '{"equipment_id":1,"failure_mode":"bearing_failure","defer_maintenance_days":3}'
check "POST simulate decision" POST "/simulate/decision" 200 '{"equipment_id":1,"mode":"delay","delay_hours":72}'

echo ""
echo "--- Analytics ---"
check "GET analytics plant" GET "/analytics/plant"
check "GET business impact" GET "/analytics/business-impact"
check "GET executive summary" GET "/analytics/executive-summary"

echo ""
echo "--- Operations ---"
check "GET logbook" GET "/logbook"
check "GET logbook summary" GET "/logbook/summary"
check "GET logbook timeline" GET "/logbook/timeline/1"
check "GET history" GET "/history/1"
check "GET spares" GET "/spares"
check "GET procurement" GET "/procurement"
check "GET delay logs" GET "/delay-logs"
check "GET scheduler reminders" GET "/scheduler/reminders"
check "GET scheduler plan" GET "/scheduler/plan"

echo ""
echo "--- Documents & Reports ---"
check "GET documents" GET "/documents"
check "GET reports list" GET "/reports"

echo ""
echo "--- PDF Export ---"
check_pdf "PDF decision export" '{"report_type":"decision","equipment_id":1,"payload":{"equipment_code":"BF-001","recommendation":{"action":"Test"}}}'

echo ""
echo "=== Results: $PASS passed, $FAIL failed, $SKIP skipped ==="
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
