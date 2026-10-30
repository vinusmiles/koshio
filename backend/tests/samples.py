"""Made-up statements shaped like real Indian bank and card exports."""
import io

from openpyxl import Workbook


def hdfc_csv() -> bytes:
    # HDFC-style: account details first, then the table, then a summary footer.
    return """HDFC BANK Ltd.,,,,,,
Account No :,50100XXXXXX4821,,,,,
Statement From : 01/10/26 To : 31/10/26,,,,,,
,,,,,,
Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/10/26,SALARY OCT 2026 ONEBEAT,0000412345678,01/10/26,,"92,000.00","1,02,000.00"
03/10/26,UPI-RATNADEEP SUPER MARKET-ratnadeep@ybl-YESB0YBLUPI-427612345678-Groceries,0000427612345678,03/10/26,"2,340.50",,"99,659.50"
05/10/26,UPI-SWIGGY-swiggy@icici-ICIC0DC0099-427798765432-Order,0000427798765432,05/10/26,640.00,,"99,019.50"
07/10/26,NWD-XXXX4821-SBIN0012345-HYDERABAD,0000000012345,07/10/26,"5,000.00",,"94,019.50"
12/10/26,BILLDESK SBI CARD PAYMENT,0000528811223,12/10/26,"6,200.00",,"87,819.50"
15/10/26,UPI-TSSPDCL-tsspdcl@sbi-SBIN0000001-428112233445-Electricity,0000428112233445,15/10/26,"1,450.00",,"86,369.50"
20/10/26,UPI-CHAI POINT-chaipoint@ybl-YESB0YBLUPI-428399887766-Tea,0000428399887766,20/10/26,50.00,,"86,319.50"
20/10/26,UPI-CHAI POINT-chaipoint@ybl-YESB0YBLUPI-428399887767-Tea,0000428399887767,20/10/26,50.00,,"86,269.50"
22/10/26,IMPS REFUND AMAZON,0000529900112,22/10/26,,499.00,"86,768.50"
,,,,,,
STATEMENT SUMMARY :-,,,,,,
Opening Balance,Dr Count,Cr Count,Debits,Credits,Closing Bal,
"10,000.00",7,2,"15,730.50","92,499.00","86,768.50",
""".encode()


def sbi_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["State Bank of India"])
    ws.append(["Account Name", "ASHA VERMA"])
    ws.append([])
    ws.append(["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"])
    ws.append(["5 Oct 2026", "5 Oct 2026", "UPI/DR/427700001111/ZEPTO MARKETPLACE/YESB/zepto@ybl/order", "427700001111", 812.0, None, 50000.0])
    ws.append(["6 Oct 2026", "6 Oct 2026", "UPI/CR/427700002222/RAVI KUMAR/HDFC/ravi@okhdfc/dinner share", "427700002222", None, 750.0, 50750.0])
    ws.append(["9 Oct 2026", "9 Oct 2026", "ATM WDL ATM CASH 1234 HYDERABAD", "", 2000.0, None, 48750.0])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def card_csv() -> bytes:
    return """Date,Transaction Details,Amount (in Rs.)
02/10/2026,AMAZON PAY INDIA PVT LTD BANGALORE,"1,899.00 Dr"
04/10/2026,HPCL PETROL PUMP HYDERABAD,"3,100.00 Dr"
11/10/2026,PAYMENT RECEIVED - THANK YOU,"6,200.00 Cr"
14/10/2026,AMAZON REFUND,499.00 Cr
18/10/2026,NETFLIX.COM MUMBAI,649.00 Dr
25/10/2026,LATE PAYMENT FEE,500.00 Dr
""".encode()


def signed_csv(rows: list[tuple[str, str, str]]) -> bytes:
    lines = ["Date,Description,Amount"] + [f"{d},{desc},{amt}" for d, desc, amt in rows]
    return ("\n".join(lines) + "\n").encode()


def many_rows(n: int = 100) -> bytes:
    lines = ["Transaction Date,Description,Debit,Credit"]
    for i in range(n):
        day = i % 16 + 13  # days 13-28 can only be day-first
        lines.append(f"{day:02d}-09-2026,Purchase number {i},{100 + i}.00,")
    return ("\n".join(lines) + "\n").encode()
