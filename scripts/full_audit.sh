#!/usr/bin/env bash
# Full system audit — every API endpoint + write operations
set -uo pipefail
API="http://127.0.0.1:8000/api/v1"
PASS=0; FAIL=0; WARN=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ✗ $1 — $2"; FAIL=$((FAIL+1)); }
warn() { echo "  ! $1 — $2"; WARN=$((WARN+1)); }

check() {
  local name="$1" method="$2" path="$3" expect="${4:-200}" body="${5:-}"
  local args=(-s -o /tmp/audit_body -w "%{http_code}" -X "$method")
  [[ -n "$TOKEN" ]] && args+=(-H "Authorization: Bearer $TOKEN")
  [[ -n "$body" ]] && args+=(-H "Content-Type: application/json" -d "$body")
  code=$(curl "${args[@]}" "$API$path" 2>/dev/null || echo "000")
  if [[ "$code" == "$expect" ]]; then ok "$name"; else bad "$name" "HTTP $code (expected $expect)"; fi
}

check_pdf() {
  local name="$1" body="$2"
  code=$(curl -s -o /tmp/audit.pdf -w "%{http_code}" -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "$body" "$API/reports/pdf/export" 2>/dev/null || echo "000")
  if [[ "$code" == "200" ]] && [[ "$(head -c 4 /tmp/audit.pdf 2>/dev/null)" == "%PDF" ]]; then ok "$name"; else bad "$name" "HTTP $code or invalid PDF"; fi
}

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  SteelPlant Maintenance Wizard — FULL SYSTEM AUDIT       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Infrastructure ──
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)
[[ "$code" == "200" ]] && ok "Backend /health" || bad "Backend /health" "HTTP $code"

for route in / /home /dashboard /monitor /diagnose /chat /priority /alerts /scheduler /simulate /logbook /delays /history /reports /spares /knowledge /analytics /how-it-works /credits /equipment; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000$route")
  [[ "$code" == "200" ]] && ok "Frontend $route" || bad "Frontend $route" "HTTP $code"
done

# ── Auth ──
echo ""
echo "── Auth ──"
LOGIN=$(curl -s -X POST "$API/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=engineer@steelplant.com&password=demo1234")
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
[[ -n "$TOKEN" ]] && ok "Login engineer@steelplant.com" || { bad "Login" "no token"; exit 1; }
check "GET /auth/me" GET "/auth/me"

SUP=$(curl -s -X POST "$API/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=supervisor@steelplant.com&password=demo1234")
ST=$(echo "$SUP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
[[ -n "$ST" ]] && ok "Login supervisor@steelplant.com" || bad "Login supervisor" "no token"

# ── Equipment ──
echo ""
echo "── Equipment & Dashboard ──"
check "GET /equipment" GET "/equipment"
check "GET /dashboard" GET "/equipment/dashboard"
check "GET /plant-twin" GET "/equipment/plant-twin"
check "GET /priority" GET "/equipment/priority"
check "GET /spares/all" GET "/equipment/spares/all"
for id in 1 2 3 4 5; do
  check "GET /equipment/$id" GET "/equipment/$id"
  check "GET /equipment/$id/sensors" GET "/equipment/$id/sensors"
  check "GET /equipment/$id/predictions" GET "/equipment/$id/predictions"
  check "GET /equipment/$id/health" GET "/equipment/$id/health"
  check "GET /equipment/$id/maintenance" GET "/equipment/$id/maintenance"
done

# ── Monitor & Alerts ──
echo ""
echo "── Monitor & Alerts ──"
for id in 1 2 3 4 5; do
  check "GET /monitor/live/$id" GET "/monitor/live/$id"
done
check "GET /alerts" GET "/alerts"
check "GET /alerts?status=open" GET "/alerts?status=open"
check "GET /alerts/summary" GET "/alerts/summary"

ALERT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" "$API/alerts?status=open&limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
if [[ -n "$ALERT_ID" ]]; then
  check "PATCH /alerts/$ALERT_ID/acknowledge" PATCH "/alerts/$ALERT_ID/acknowledge" 200
else
  warn "Alert acknowledge" "no open alerts"
fi

# ── AI Pipeline ──
echo ""
echo "── AI & Diagnosis ──"
check "GET /chat/conversations" GET "/chat/conversations"
check "POST /chat" POST "/chat" 200 '{"message":"Summarize fleet health","equipment_id":1}'
check "POST /diagnose" POST "/diagnose" 200 '{"equipment_id":1,"symptoms":"high vibration bearing noise","operating_conditions":"normal"}'
check "GET /feedback/stats" GET "/feedback/stats"
check "POST /feedback" POST "/feedback" 200 '{"equipment_id":1,"source_type":"diagnose","rating":5,"approved":true,"query":"audit test","recommendation":"test rec"}'

# ── Simulator ──
echo ""
echo "── Decision Simulator ──"
check "GET /simulate/dependencies" GET "/simulate/dependencies"
check "POST /simulate (failure)" POST "/simulate" 200 '{"equipment_id":1,"failure_mode":"bearing_failure","defer_maintenance_days":3}'
check "POST /simulate/decision (3d delay)" POST "/simulate/decision" 200 '{"equipment_id":1,"mode":"delay","delay_hours":72}'
check "POST /simulate/decision (immediate)" POST "/simulate/decision" 200 '{"equipment_id":1,"mode":"immediate_failure"}'
check "POST /simulate/decision (24h)" POST "/simulate/decision" 200 '{"equipment_id":1,"mode":"delay","delay_hours":24}'
check "POST /simulate/decision (custom)" POST "/simulate/decision" 200 '{"equipment_id":1,"mode":"delay","custom_delay_hours":120}'

# ── Analytics ──
echo ""
echo "── Analytics ──"
PLANT=$(curl -s -H "Authorization: Bearer $TOKEN" "$API/analytics/plant")
echo "$PLANT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'roi' in d and 'business_impact' in d; print('  ✓ analytics/plant has roi+business_impact')" && PASS=$((PASS+1)) || bad "analytics/plant schema" "missing fields"
check "GET /analytics/business-impact" GET "/analytics/business-impact"
check "GET /analytics/executive-summary" GET "/analytics/executive-summary"

# ── Operations ──
echo ""
echo "── Operations ──"
check "GET /logbook" GET "/logbook"
check "GET /logbook?auto_only=true" GET "/logbook?auto_only=true"
check "GET /logbook/summary" GET "/logbook/summary"
check "GET /logbook/timeline/1" GET "/logbook/timeline/1"
check "POST /logbook" POST "/logbook" 200 '{"equipment_id":1,"entry_type":"observation","title":"Audit entry","description":"Full audit test"}'
check "GET /history/1" GET "/history/1"
check "GET /spares" GET "/spares"
check "GET /procurement" GET "/procurement"
check "GET /delay-logs" GET "/delay-logs"
check "POST /delay-logs" POST "/delay-logs" 200 '{"equipment_id":1,"delay_hours":1,"reason":"Audit","severity":"low"}'

# ── Scheduler ──
echo ""
echo "── Scheduler ──"
check "GET /scheduler/reminders" GET "/scheduler/reminders"
check "GET /scheduler/plan" GET "/scheduler/plan"
check "POST /scheduler/reminders" POST "/scheduler/reminders" 200 '{"equipment_id":1,"title":"Audit reminder","reminder_at":"2026-06-25T10:00:00Z","notes":"audit"}'

# ── Documents & Reports ──
echo ""
echo "── Documents & Reports ──"
check "GET /documents" GET "/documents"
DOC_ID=$(curl -s -H "Authorization: Bearer $TOKEN" "$API/documents" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
[[ -n "$DOC_ID" ]] && check "GET /documents/$DOC_ID/content" GET "/documents/$DOC_ID/content" || warn "Document content" "no documents"
check "GET /reports" GET "/reports"
check "POST /reports/generate" POST "/reports/generate" 200 '{"report_type":"priority","equipment_id":1,"title":"Audit Report"}'
REPORT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" "$API/reports" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
[[ -n "$REPORT_ID" ]] && check "GET /reports/$REPORT_ID" GET "/reports/$REPORT_ID" || warn "Report detail" "no reports"
[[ -n "$REPORT_ID" ]] && check "GET /reports/$REPORT_ID/pdf" GET "/reports/$REPORT_ID/pdf" || true

# ── PDF Exports ──
echo ""
echo "── PDF Exports ──"
check_pdf "PDF diagnosis" '{"report_type":"diagnosis","equipment_id":1,"payload":{"equipment_code":"BF-001","probable_causes":[{"cause":"Bearing wear","confidence":0.8}]}}'
check_pdf "PDF scenario" '{"report_type":"scenario","equipment_id":1,"payload":{"equipment_code":"BF-001","scenario_label":"Bearing failure","contingency_plan":["Step 1"]}}'
check_pdf "PDF decision" '{"report_type":"decision","equipment_id":1,"payload":{"equipment_code":"BF-001","recommendation":{"action":"Maintain today","reason":"Lowest risk"},"comparison":[]}}'
check_pdf "PDF priority" '{"report_type":"priority","equipment_id":1,"payload":{"equipment_code":"BF-001","priority_score":85}}'
check_pdf "PDF executive" '{"report_type":"executive","payload":{}}'
check_pdf "PDF alert" '{"report_type":"alert","payload":{"equipment_code":"BF-001","title":"Test alert","message":"Audit"}}'
check_pdf "PDF maintenance_plan" '{"report_type":"maintenance_plan","payload":{"tasks":[{"equipment_code":"BF-001","task":"Inspect bearing","urgency":"high"}]}}'

# ── Schema validation ──
echo ""
echo "── Response schema checks ──"
curl -s -H "Authorization: Bearer $TOKEN" "$API/simulate/decision" -H "Content-Type: application/json" \
  -d '{"equipment_id":1,"mode":"delay","delay_hours":72}' > /tmp/decision.json
python3 << 'PY'
import json, sys
d = json.load(open("/tmp/decision.json"))
required = ["current_state","selected_scenario","comparison","recommendation","reasoning_chain","financial_impact","spare_availability","downstream_impact"]
missing = [k for k in required if k not in d]
if missing:
    print(f"  ✗ decision response missing: {missing}")
    sys.exit(1)
print("  ✓ decision response schema complete")
PY
[[ $? -eq 0 ]] && PASS=$((PASS+1)) || FAIL=$((FAIL+1))

curl -s -H "Authorization: Bearer $TOKEN" "$API/diagnose" -H "Content-Type: application/json" \
  -d '{"equipment_id":1,"symptoms":"vibration","operating_conditions":"normal"}' > /tmp/diag.json
python3 << 'PY'
import json, sys
d = json.load(open("/tmp/diag.json"))
required = ["equipment_code","probable_causes","risk_level"]
missing = [k for k in required if k not in d]
if missing:
    print(f"  ✗ diagnose response missing: {missing}")
    sys.exit(1)
print("  ✓ diagnose response schema complete")
PY
[[ $? -eq 0 ]] && PASS=$((PASS+1)) || FAIL=$((FAIL+1))

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  PASSED: $PASS   FAILED: $FAIL   WARNINGS: $WARN"
echo "══════════════════════════════════════════════════════════"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
