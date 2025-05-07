# MCP-Gold-Investment

## 개발 스케치

### Tools

| Tool                  | 기능                                             |
| --------------------- | ---------------------------------------------- |
| latest_gold_price       | 한국 금거래소 url을 통해 금 시세 정보 확인                     |
| ledger          | 개인 매수 / 매도 내역 CRUD (SQLite or CSV)             |
| profit_calc      | Ledger + Price + FX → 평균단가·보유량·미실현/실현 손익 계산    |
| gold_buy_alert    | 매일 09:00 KST 시세 체크 → 7일 평균 대비 n %↓면 메일 발송      |
| investor_profile | Knowledge Graph기반 대화이력 분석 → 위험 성향·선호 자산 프로필 생성 |
| make_chart           | 시세·수익 곡선 시각화                                   |
| kg_memory         | 대화 내용을 Knowledge Graph로 저장·검색                  |

