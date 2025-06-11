# KIS Trading MCP Server

## 개요

이 프로젝트는 `FastMCP` 프레임워크와 `python-kis` 라이브러리를 사용하여 한국투자증권(KIS) API와 연동하는 MCP(Model Context Protocol) 서버입니다. LLM 기반의 애플리케이션 또는 에이전트가 이 MCP 서버를 통해 한국투자증권의 계좌 정보 조회, 주식 시세 확인, 주문 실행 등의 기능을 수행할 수 있도록 인터페이스를 제공합니다.

서버는 **STDIO**와 **Streamable HTTP** 두 가지 transport 방식을 지원하여 다양한 클라이언트 환경에서 사용할 수 있습니다.

## 주요 기능

- **계좌 잔고 조회:** 총 평가금액, 순자산, 예수금, 보유 주식 목록 및 상세 정보 조회
- **주식 현재가 조회:** 특정 종목의 현재가, 등락률, 거래량 등 시세 정보 조회
- **주식 주문 실행:** 지정가 또는 시장가로 매수/매도 주문 제출
- **미체결 주문 조회:** 현재 계좌의 미체결 주문 목록 확인
- **주문 취소:** 미체결된 주문 취소
- **매수/매도 가능 수량 조회:** 현금 잔고 기반 매수 가능 금액/수량, 보유 주식 기반 매도 가능 수량 확인
- **호가 정보 조회:** 실시간 매수/매도 호가와 잔량 정보 확인
- **차트 데이터 조회:** 일/주/월봉 OHLCV 데이터 조회
- **손익 현황 조회:** 기간별 실현/미실현 손익, 일별 체결 내역 확인
- **시장 운영 상태 조회:** 한국 주식 시장의 실시간 운영 상태 및 거래 시간 정보

## 사용된 주요 라이브러리

- **FastMCP:** MCP 서버를 빠르고 쉽게 구축하기 위한 Python 프레임워크입니다.
- **python-kis:** 한국투자증권 API를 Python 환경에서 사용하기 위한 라이브러리입니다.
- **Pydantic:** 데이터 유효성 검사 및 설정 관리를 위해 사용됩니다.

## 실행 방법

    서버는 두 가지 transport 방식을 지원합니다:

    **STDIO 모드 (기본값, Claude Desktop 등 MCP 클라이언트용):**
    ```bash
    python main.py
    # 또는 명시적으로
    python main.py stdio
    ```

    **HTTP 모드 (웹 기반 클라이언트용):**
    ```bash
    python main.py http
    # 또는
    python main.py streamable-http
    ```

    **환경변수로 transport 방식 설정:**
    ```bash
    # Windows PowerShell
    $env:MCP_TRANSPORT="streamable-http"
    python main.py

    # macOS/Linux
    export MCP_TRANSPORT="streamable-http"
    python main.py
    ```

    - **STDIO 모드:** Claude Desktop, MCP 인스펙터 등 표준 MCP 클라이언트와 호환
    - **HTTP 모드:** 웹 브라우저나 HTTP 클라이언트를 통해 `http://127.0.0.1:8000/mcp`에서 접근 가능

## MCP Tool 목록

서버가 제공하는 주요 Tool들은 다음과 같습니다 (자세한 파라미터는 `main.py`의 각 tool 데코레이터와 docstring 참조):

**기본 거래 기능:**
- `get_account_balance()`: 계좌 잔고 조회
- `get_stock_quote(stock_code: str)`: 주식 현재가 조회
- `place_stock_order(stock_code: str, order_type: Literal["buy", "sell"], quantity: int, price: Optional[int], order_method: Literal["limit", "market"])`: 주식 주문
- `get_pending_orders()`: 미체결 주문 조회
- `cancel_stock_order(order_id: str)`: 주문 취소

**거래 지원 기능:**
- `get_buyable_amount(stock_code: str, price: Optional[int])`: 매수 가능 금액과 수량 조회
- `get_sellable_quantity(stock_code: str)`: 매도 가능 수량 조회

**시장 데이터 조회:**
- `get_stock_orderbook(stock_code: str)`: 호가 정보 조회
- `get_stock_chart(stock_code: str, period: Literal["day", "week", "month"], count: int)`: 차트 데이터 조회
- `get_market_status()`: 시장 운영 상태 조회

**손익 및 내역 분석:**
- `get_period_profit_loss(start_date: str, end_date: str)`: 기간 손익 현황 조회
- `get_daily_executions(date: str)`: 일별 체결 내역 조회

## 주의사항

-   `python-kis` 라이브러리에서 반환하는 객체의 속성명은 KIS API 응답 필드명과 다를 수 있거나 라이브러리 버전에 따라 변경될 수 있습니다. `main.py` 내의 Tool 함수들은 `getattr`을 사용하여 유연하게 대처하려 했으나, 실제 운영 전 반드시 테스트하고 필요시 객체 속성명을 정확히 확인하여 코드를 조정하십시오.
-   실전 투자 시에는 모든 API 요청 및 주문 실행에 각별한 주의를 기울여야 합니다. 충분한 테스트 후 사용하십시오.
