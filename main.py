import asyncio
import os
from decimal import Decimal
from typing import Annotated, Literal, Any
from pydantic import Field

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from pykis import (
    PyKis,
    KisAccount,
    KisStock,
    KisQuote,
    KisOrder,
    KisBalance,
    KisPendingOrders,
)

# --- KIS API Configuration ---
KIS_APP_KEY: str = os.getenv("KIS_APP_KEY", "YOUR_MOCK_APP_KEY")
KIS_APP_SECRET: str = os.getenv("KIS_APP_SECRET", "YOUR_MOCK_APP_SECRET")
KIS_ACCOUNT_NO: str = os.getenv("KIS_ACCOUNT_NO", "YOUR_MOCK_ACCOUNT_NO-01")
KIS_HTS_ID: str = os.getenv("KIS_HTS_ID", "YOUR_MOCK_HTS_ID")
VIRTUAL_TRADING: bool = os.getenv("VIRTUAL_TRADING", "true").lower() == "true"

kis: PyKis = PyKis(
    id=KIS_HTS_ID,
    appkey=KIS_APP_KEY if not VIRTUAL_TRADING else None,
    secretkey=KIS_APP_SECRET if not VIRTUAL_TRADING else None,
    virtual_id=KIS_HTS_ID if VIRTUAL_TRADING else None,
    virtual_appkey=KIS_APP_KEY if VIRTUAL_TRADING else None,
    virtual_secretkey=KIS_APP_SECRET if VIRTUAL_TRADING else None,
    account=KIS_ACCOUNT_NO,
    keep_token=True,
)

if VIRTUAL_TRADING:
    print("한국투자증권 모의투자 API 클라이언트가 초기화되었습니다.")
else:
    print("한국투자증권 실전투자 API 클라이언트가 초기화되었습니다.")
    print(
        "⚠️ 경고: 실전투자 모드입니다. 실제 자금 거래가 발생할 수 있으니 주의하십시오."
    )


# --- FastMCP 서버 설정 ---
mcp: FastMCP[None] = FastMCP(
    name="KIS Trading MCP Server",
    instructions="한국투자증권 API를 통해 주식 거래, 계좌 조회, 주문 관리를 할 수 있는 MCP 서버입니다. 실시간 주가 조회, 매수/매도 주문, 잔고 확인, 미체결 주문 관리 등의 기능을 제공합니다.",
)


# --- KIS API 연동 MCP Tools ---
@mcp.tool(
    name="get_account_balance",
    description="한국투자증권 계좌의 전체 잔고 정보를 조회합니다. 총 자산, 현금 잔고, 보유 종목별 평가 정보를 포함합니다.",
    tags={"account", "balance", "portfolio"},
)
async def get_account_balance(ctx: Context) -> dict:
    """
    한국투자증권 계좌의 잔고 정보를 조회합니다.

    Returns:
        dict: 계좌 잔고 정보
            - total_evaluation_amount: 총자산금액 (현금 + 주식 평가금액)
            - net_asset_amount: 순자산금액
            - cash_balance: 출금 가능 현금 잔고
            - securities_evaluation_amount: 보유 주식 총 평가금액
            - holdings: 보유 종목 상세 정보 리스트
                - item_name: 종목명
                - quantity: 보유 수량
                - average_purchase_price: 평균 매입가
                - current_price: 현재가
                - evaluation_amount: 평가금액
                - profit_loss: 평가 손익
                - profit_loss_ratio: 손익률(%)
    """
    try:
        account: KisAccount = kis.account()
        balance: KisBalance = await asyncio.to_thread(account.balance)

        holdings_data: list[dict[str, float | int | str | Any]] = []
        if hasattr(balance, "stocks") and balance.stocks:
            for stock_item in balance.stocks:  # stock_item is KisBalanceStock
                holdings_data.append(
                    {
                        "item_name": stock_item.name,  # 상품명
                        "quantity": stock_item.quantity,  # 보유수량
                        "average_purchase_price": stock_item.purchase_price,  # 매입평균가격
                        "current_price": stock_item.current_price,  # 현재가
                        "evaluation_amount": stock_item.current_amount,  # 평가금액
                        "profit_loss": stock_item.profit,  # 평가손익금액
                        "profit_loss_ratio": stock_item.profit_rate,  # 평가손익률
                    }
                )

        return {
            "total_evaluation_amount": balance.amount,  # 총자산금액 (원화, 보유종목 + 예수금)
            "net_asset_amount": balance.total,  # 총평가금액 (원화, 보유종목 + 예수금)
            "cash_balance": balance.withdrawable_amount,  # 총출금가능금액 (원화)
            "securities_evaluation_amount": balance.current_amount,  # 보유종목 총평가금액 (원화)
            "holdings": holdings_data,
        }
    except Exception as e:
        raise ToolError(f"계좌 잔고 조회 중 오류가 발생했습니다: {e}")


@mcp.tool(
    name="get_stock_quote",
    description="지정된 종목 코드의 실시간 주식 시세 정보를 조회합니다. 현재가, 등락률, 거래량, 시가총액 등의 정보를 제공합니다.",
    tags={"stock", "quote", "price", "market-data"},
)
async def get_stock_quote(
    ctx: Context,
    stock_code: Annotated[
        str,
        Field(
            description="조회할 주식의 6자리 종목 코드 (예: '005930' - 삼성전자, '000660' - SK하이닉스, '035420' - NAVER)",
            pattern=r"^\d{6}$",
            examples=["005930", "000660", "035420"],
        ),
    ],
) -> dict:
    """
    지정된 종목의 현재 주식 시세를 조회합니다.

    Args:
        stock_code: 6자리 주식 종목 코드

    Returns:
        dict: 주식 시세 정보
            - stock_code: 종목 코드
            - current_price: 현재가 (원)
            - change: 전일 대비 등락금액 (원)
            - change_percent: 등락률 (%)
            - volume: 당일 거래량 (주)
            - trading_value: 당일 거래대금 (원)
            - market_cap: 시가총액 (원)
            - open_price: 시가 (원)
            - high_price: 당일 최고가 (원)
            - low_price: 당일 최저가 (원)
    """
    try:
        stock: KisStock = kis.stock(stock_code)
        quote: KisQuote = await asyncio.to_thread(stock.quote)

        return {
            "stock_code": stock_code,
            "current_price": quote.price,  # 현재가
            "change": quote.change,  # 전일 대비
            "change_percent": quote.rate,  # 등락률
            "volume": quote.volume,  # 거래량
            "trading_value": quote.amount,  # 거래대금
            "market_cap": quote.market_cap,  # 시가총액
            "open_price": quote.open,  # 시가
            "high_price": quote.high,  # 고가
            "low_price": quote.low,  # 저가
        }
    except Exception as e:
        raise ToolError(f"종목 '{stock_code}' 시세 조회 중 오류가 발생했습니다: {e}")


@mcp.tool(
    name="place_stock_order",
    description="지정된 조건으로 주식 매수 또는 매도 주문을 제출합니다. 지정가 주문(price 필수)과 시장가 주문(price=None)을 모두 지원합니다.",
    tags={"trading", "order", "buy", "sell"},
)
async def place_stock_order(
    ctx: Context,
    stock_code: Annotated[
        str,
        Field(
            description="주문할 주식의 6자리 종목 코드",
            pattern=r"^\d{6}$",
            examples=["005930", "000660", "035420"],
        ),
    ],
    order_type: Annotated[
        Literal["buy", "sell"],
        Field(description="주문 유형: 'buy' (매수) 또는 'sell' (매도)"),
    ],
    quantity: Annotated[
        int, Field(description="주문 수량 (1주 이상)", gt=0, examples=[10, 100, 1000])
    ],
    price: Annotated[
        int | None,
        Field(
            description="주문 가격 (원). 지정가 주문 시 필수, 시장가 주문 시 None (미전달)",
            ge=0,
            examples=[50000, 100000, 200000],
        ),
    ] = None,
    order_method: Annotated[
        Literal["limit", "market"],
        Field(description="주문 방식: 'limit' (지정가) 또는 'market' (시장가)"),
    ] = "limit",
) -> dict:
    """
    주식 매수/매도 주문을 제출합니다.

    Args:
        stock_code: 6자리 종목 코드
        order_type: 주문 유형 (buy/sell)
        quantity: 주문 수량 (1주 이상)
        price: 주문 가격 (지정가 주문 시 필수, 시장가 주문 시 None)
        order_method: 주문 방식 (limit/market)

    주문 방식별 동작:
        - 지정가 주문: price 파라미터 필수 (예: price=50000)
        - 시장가 주문: price 파라미터 무시됨 (None 권장)

    Returns:
        dict: 주문 결과 정보
            - order_id: 주문 번호
            - stock_code: 종목 코드
            - order_type: 주문 유형
            - order_method: 주문 방식
            - quantity: 주문 수량
            - price: 주문 가격 (시장가는 "market")
            - status: 주문 상태
            - message: 처리 결과 메시지
    """
    try:
        stock: KisStock = kis.stock(stock_code)
        order_result: KisOrder | None = None

        if order_type == "buy":
            if order_method == "limit" and price is not None and price > 0:
                # 지정가 매수
                order_result = await asyncio.to_thread(
                    stock.buy, qty=quantity, price=price
                )
            else:
                # 시장가 매수 (가격 파라미터 없음)
                order_result = await asyncio.to_thread(stock.buy, qty=quantity)
        elif order_type == "sell":
            if order_method == "limit" and price is not None and price > 0:
                # 지정가 매도
                order_result = await asyncio.to_thread(
                    stock.sell, qty=quantity, price=price
                )
            else:
                # 시장가 매도 (가격 파라미터 없음)
                order_result = await asyncio.to_thread(stock.sell, qty=quantity)

        if order_result:
            order_id: str = order_result.number
            is_pending: bool = order_result.pending

            return {
                "order_id": order_id,
                "stock_code": stock_code,
                "order_type": order_type,
                "order_method": order_method,
                "quantity": quantity,
                "price": (
                    price if order_method == "limit" and price is not None else "market"
                ),
                "status": "pending" if is_pending else "executed_or_failed_or_unknown",
                "message": (
                    "주문이 성공적으로 제출되었습니다."
                    if order_id
                    else "주문 제출에 실패했거나 주문번호를 받지 못했습니다."
                ),
            }
        else:
            raise ToolError("주문 객체를 생성하지 못했습니다.")

    except Exception as e:
        raise ToolError(
            f"종목 '{stock_code}' {order_type} 주문 중 오류가 발생했습니다: {e}"
        )


@mcp.tool(
    name="get_pending_orders",
    description="현재 계좌의 모든 미체결 주문 목록을 조회합니다. 주문 번호, 종목, 수량, 가격, 미체결 수량 등의 정보를 제공합니다.",
    tags={"orders", "pending", "unfilled"},
)
async def get_pending_orders(ctx: Context) -> list[dict]:
    """
    현재 계좌의 미체결 주문 목록을 조회합니다.

    Returns:
        list[dict]: 미체결 주문 목록
            각 주문 정보:
            - order_id: 주문 번호
            - stock_code: 종목 코드
            - order_type: 주문 유형 (buy/sell)
            - quantity: 총 주문 수량
            - pending_quantity: 미체결 수량
            - price: 주문 가격
            - order_time: 주문 시간
    """
    try:
        account: KisAccount = kis.account()
        pending_orders_iter: KisPendingOrders = await asyncio.to_thread(
            account.pending_orders
        )

        orders_list: list[dict[str, Decimal | str]] = []
        if pending_orders_iter:
            for order_item in pending_orders_iter:
                order_no: str = order_item.number
                stock_code_val: str = order_item.symbol

                order_type_val: Literal["buy", "sell"] = order_item.type

                qty_val: Decimal = order_item.qty

                price_val_raw: Decimal | None = order_item.order_price
                price_val: Decimal = (
                    price_val_raw if price_val_raw is not None else Decimal("0")
                )

                order_dt_val: str = (
                    str(order_item.time_kst)
                    if hasattr(order_item, "time_kst")
                    and order_item.time_kst is not None
                    else "N/A"
                )

                pending_qty_val: Decimal = order_item.pending_qty

                orders_list.append(
                    {
                        "order_id": order_no,
                        "stock_code": stock_code_val,
                        "order_type": order_type_val,
                        "quantity": qty_val,
                        "pending_quantity": pending_qty_val,
                        "price": price_val,
                        "order_time": order_dt_val,
                    }
                )
        return orders_list
    except Exception as e:
        raise ToolError(f"미체결 주문 조회 중 오류가 발생했습니다: {e}")


@mcp.tool(
    name="cancel_stock_order",
    description="지정된 주문 번호의 미체결 주문을 취소합니다. 이미 체결된 주문은 취소할 수 없습니다.",
    tags={"orders", "cancel", "modify"},
)
async def cancel_stock_order(
    ctx: Context,
    order_id: Annotated[
        str,
        Field(
            description="취소할 주문의 고유 번호 (주문 제출 시 또는 미체결 주문 조회에서 확인 가능)",
            examples=["20240101-123456", "ORD240101001"],
        ),
    ],
) -> dict:
    """
    지정된 주문 ID의 미체결 주문을 취소합니다.

    Args:
        order_id: 취소할 주문의 고유 번호

    Returns:
        dict: 취소 처리 결과
            - order_id: 주문 번호
            - status: 처리 상태 ("cancelled", "not_cancellable")
            - message: 처리 결과 메시지
    """
    try:
        account: KisAccount = kis.account()
        target_order: KisOrder | None = None
        pending_orders_iter: KisPendingOrders = await asyncio.to_thread(
            account.pending_orders
        )

        if pending_orders_iter:
            for order_obj in pending_orders_iter:
                current_order_id: str = order_obj.number
                if current_order_id == order_id:
                    target_order = order_obj
                    break

        if target_order and target_order.pending:
            await asyncio.to_thread(target_order.cancel)
            return {
                "order_id": order_id,
                "status": "cancelled",
                "message": f"주문번호 {order_id} 취소 요청이 성공적으로 제출되었습니다.",
            }
        elif target_order:
            return {
                "order_id": order_id,
                "status": "not_cancellable",
                "message": f"주문번호 {order_id}은(는) 이미 체결되었거나 취소할 수 없는 상태입니다.",
            }
        else:
            raise ToolError(
                f"주문번호 '{order_id}'를 찾을 수 없습니다. 주문번호를 확인해 주세요."
            )

    except Exception as e:
        raise ToolError(f"주문 '{order_id}' 취소 중 오류가 발생했습니다: {e}")


# --- 서버 실행 ---
if __name__ == "__main__":
    import sys

    # 기본값은 stdio (MCP 클라이언트와의 호환성을 위해)
    transport = "stdio"
    host = "127.0.0.1"
    port = 8000
    path = "/mcp"

    # 명령행 인수로 transport 방식 선택
    if len(sys.argv) > 1:
        if sys.argv[1] in ["http", "streamable-http"]:
            transport = "streamable-http"
        elif sys.argv[1] == "stdio":
            transport = "stdio"

    # 환경변수로도 설정 가능
    transport: str = os.getenv("MCP_TRANSPORT", transport)

    if transport == "streamable-http":
        print(f"MCP 서버 '{mcp.name}'를 HTTP 모드로 시작합니다.")
        print(f"URL: http://{host}:{port}{path}")
        print("Transport: streamable-http")
        mcp.run(transport="streamable-http", host=host, port=port, path=path)
    else:
        print(f"MCP 서버 '{mcp.name}'를 STDIO 모드로 시작합니다.")
        print("Transport: stdio")
        mcp.run(transport="stdio")
