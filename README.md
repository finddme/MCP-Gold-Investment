# MCP-Gold-Investment

## 개발 스케치

### Tools

| Tool                  | 기능                                             | 개발 여부 | 추후 보완 사항                                      |
| --------------------- | ---------------------------------------------- | ----- | --------------------------------------------- |
| GoldPriceServer       | 한국 금거래소 url을 통해 금 시세 정보 확인                     | o     | 한국금거래소 페이지 "구매가" "판매가" 크롤링 불가<br>가능한 방안 찾아 보완 |
| LedgerServer          | 개인 매수 / 매도 내역 CRUD (SQLite or CSV)             | o     |                                               |
| ProfitCalcServer      | Ledger + Price + FX → 평균단가·보유량·미실현/실현 손익 계산    | o     |                                               |
| GoldBuyAlertServer    | 매일 09:00 KST 시세 체크 → 7일 평균 대비 n %↓면 메일 발송      | x     |                                               |
| InvestorProfileServer | Knowledge Graph기반 대화이력 분석 → 위험 성향·선호 자산 프로필 생성 | x     |                                               |
| Memory Server         | 대화 내용을 Knowledge Graph로 저장·검색                  | x     |                                               |
