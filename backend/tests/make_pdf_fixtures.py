"""Builds the made-up PDF statements in fixtures/. Run once after editing:
    pip install reportlab && python tests/make_pdf_fixtures.py
The PDFs are committed so the tests don't need reportlab or fonts."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "fixtures"
pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))


def page(name, rows, encrypt=None):
    """rows: list of lists of (x, text) drawn on one line each."""
    c = canvas.Canvas(str(OUT / name), pagesize=A4, encrypt=encrypt)
    y = 800
    for line in rows:
        if y < 60:
            c.showPage()
            y = 800
        c.setFont("DV", 8.5)
        for x, text in line:
            c.drawString(x, y, text)
        y -= 14
    c.save()


def phonepe():
    """Layout copied from a real PhonePe statement; every name, number and amount is invented."""
    def rec(date, time, detail, typ, amt, txn, utr, by="Paid by XXXX123456", extra=None):
        out = [[(40, date), (130, detail), (400, typ), (480, amt)],
               [(40, time), (130, f"Transaction ID {txn}")],
               [(130, f"UTR No. {utr}")]]
        if extra:
            out.append([(130, extra)])
        out.append([(130, by)])
        return out
    rows = [[(100, "Transaction Statement for 98XXXXX210")], [(100, "28 Sept, 2026 - 24 Oct, 2026")],
            [(40, "Date"), (130, "Transaction Details"), (400, "Type"), (480, "Amount")]]
    rows += rec("Oct 05, 2026", "07:32 pm", "Paid to SWIGGY", "DEBIT", "₹640", "T2610051932123456789", "427798765432")
    rows += rec("Oct 06, 2026", "01:10 pm", "Received from RAVI KUMAR", "CREDIT", "₹750", "T2610061310123456789", "427700002222", "Credited to XXXX123456")
    rows += rec("Oct 08, 2026", "09:45 am", "Paid to Zepto Marketplace Private Limited", "DEBIT", "₹1,234.50", "T2610080945123456789", "427812341234", "Paid by 652111XXXXXXXX77")
    rows += [[(40, "Oct 09, 2026"), (130, "Paid to IRCTC Payment Failed"), (400, "DEBIT"), (480, "₹2,145")],
             [(40, "11:00 am"), (130, "Transaction ID T2610091100999999999")]]
    rows += rec("Oct 20, 2026", "05:01 pm", "Paid to CHAI POINT", "DEBIT", "₹50", "T2610201701111111111", "428399887766", "Paid by UPI Lite")
    rows += rec("Oct 20, 2026", "05:40 pm", "Paid to CHAI POINT", "DEBIT", "₹50", "T2610201740222222222", "428399887799", "Paid by UPI Lite")
    rows += rec("Oct 12, 2026", "12:43 pm", "Requested by Asha Verma", "DEBIT", "₹450", "D2610121243111111111", "478200000001", "Paid by XXXXXXXXXX55")
    rows += rec("Oct 19, 2026", "01:35 pm", "Add money UPI Lite", "DEBIT", "₹1,000", "W2610191335111111111", "681600000001")
    rows += rec("Oct 10, 2026", "01:39 pm", "FASTag Recharge for TS00AB0000", "DEBIT", "₹1,000", "NB2610101339111111111",
                "689200000001", extra="Bharat Connect Transaction ID PP0000000000000000")
    rows += [[(40, "Oct 07, 2026"), (130, "Paid to"), (400, "DEBIT"), (480, "₹35")],
             [(130, "ROPPEN TRANSPORTATION SERVICES PRIVATE LIMITED")],
             [(40, "12:51 pm"), (130, "Transaction ID T2610071251111111111")],
             [(130, "UTR No. 032200000001")], [(130, "Paid by UPI Lite")]]
    rows += rec("Sept 30, 2026", "11:16 pm", "Transfer to XXXXXXXXXX55", "DEBIT", "₹5,000", "T2609302315111111111", "615200000001")
    rows += [[(200, "Page 1 of 1")], [(40, "This is a system generated statement. For any queries, contact us at https://support.phonepe.com/statement.")]]
    page("phonepe.pdf", rows)


def bhim():
    """Layout copied from a real BHIM statement; every name, number and amount is invented.
    Two rows are run together on one line, as in the real file."""
    me = "xxxxxkumar@upi(RAVI KUMAR)"
    rows = [[(40, "Customer Mobile Number: +9198XXXXX210 Transaction History from 28/09/2026 to 28/10/2026")],
            [(40, "Transaction History")],
            [(40, "Date Time Bank Name Account Number Sender Receiver Payment ID/Reference Number Pay/Collect Amount (in Rs.) DR/CR Status")],
            [(20, f"28/10/2026 06:46:48 Axis Bank Ltd. XXXX123456 {me} xxxxx11111@ybl(xxxxxxxxMART) 064648000001 PAY 50.00 DR SUCCESS")],
            [(20, f"27/10/2026 18:31:23 AXIS BANK RUPAY CREDIT CARD 652111XXXXXXXX77 {me} xxxxx22222@ybl(xxxxxxxxSHOP) 183123000002 PAY 70.00 DR SUCCESS")],
            [(20, f"24/10/2026 16:11:26 Axis Bank Ltd. XXXX123456 {me} boim-xxxxxxx55555@boi(xxxxxxxxSTOR) 161126000003 PAY 5000.00 DR FAILURE")],
            [(20, f"13/10/2026 13:02:11 HDFC BANK LTD ******9999 {me} xxxxxkumar@upi(xxxxxxxxBAKE) 130211000004 PAY 39442.00 DR SUCCESS")],
            [(20, f"11/10/2026 07:37:32 AU SFB RUPAY CREDIT CARD 653000XXXXXXXX19 {me} xxxRATPE.xxxx33333@unitype(xxxxxxxx TEA) 073732000005 PAY 90.00 DR SUCCESS11/10/2026 07:25:08 AU SFB RUPAY CREDIT CARD 653000XXXXXXXX19 {me} xxxxx44444@ybl(xxxxxxxxBAKE) 072508000006 PAY 15.00 DR SUCCESS")],
            [(20, f"08/10/2026 12:37:06 HDFC BANK LTD ******9999 {me} xpstox.brk@validhdfc(xxxxxxxx LTD) 123706000007 PAY 7700.00 DR SUCCESS")],
            [(20, f"05/10/2026 09:19:01 Axis Bank Ltd. XXXX123456 {me} N/AN/A 091901000008 PAY 638.39 DR SUCCESS")],
            [(20, f"25/10/2026 18:06:22 AU SFB RUPAY CREDIT CARD 653000XXXXXXXX19 {me} N/AN/A 180622000010 PAY 500.00 DR SUCCESS")],
            [(20, "30/09/2026 14:12:19 Axis Bank Ltd. XXXX123456 xxxxxxxhback@hdfcbank(NPCI BHIM) xxxxxkumar@upi() 104130000009 PAY 37.00 CR SUCCESS")]]
    c = canvas.Canvas(str(OUT / "bhim.pdf"), pagesize=(1200, 842))  # the real statement is landscape
    y = 800
    for line in rows:
        c.setFont("DV", 7)
        for x, text in line:
            c.drawString(x, y, text)
        y -= 14
    c.save()


def gpay():
    rows = [[(40, "Google Pay")], [(40, "Transaction statement")], [(40, "01 October 2026 - 24 October 2026")],
            [(40, "Date & time"), (150, "Transaction details"), (480, "Amount")],
            [(40, "05 Oct, 2026"), (150, "Paid to Swiggy"), (480, "₹640")],
            [(40, "07:32 PM"), (150, "UPI Transaction ID: 427798765432")],
            [(150, "Paid by HDFC Bank 4821")],
            [(40, "06 Oct, 2026"), (150, "Received from Ravi Kumar"), (480, "₹750")],
            [(40, "01:10 PM"), (150, "UPI Transaction ID: 427700002222")],
            [(150, "Paid to HDFC Bank 4821")],
            [(40, "15 Oct, 2026"), (150, "Paid to TSSPDCL"), (480, "₹1,450")],
            [(40, "08:00 AM"), (150, "UPI Transaction ID: 428112233445")],
            [(150, "Paid by HDFC Bank 4821")]]
    page("gpay.pdf", rows)


def card():
    rows = [[(40, "HDFC Bank Credit Card Statement")], [(40, "Card No: 4321 XXXX XXXX 0937")],
            [(40, "Statement Date"), (200, "15/10/2026")], [(40, "Payment Due Date"), (200, "05/11/2026")],
            [(40, "Total Amount Due"), (200, "6,148.00")], [(40, "Minimum Amount Due"), (200, "310.00")],
            [(40, "Credit Limit"), (200, "2,00,000.00")],
            [(40, "Domestic Transactions")],
            [(40, "Date"), (120, "Transaction Description"), (400, "Reward Points"), (480, "Amount (in Rs.)")],
            [(40, "02/10/2026"), (120, "AMAZON PAY INDIA PVT LTD BANGALORE"), (400, "18"), (480, "1,899.00")],
            [(40, "04/10/2026"), (120, "HPCL PETROL PUMP HYDERABAD"), (400, "31"), (480, "3,100.00")],
            [(40, "11/10/2026"), (120, "PAYMENT RECEIVED - THANK YOU"), (480, "6,200.00 Cr")],
            [(40, "14/10/2026"), (120, "AMAZON PAY INDIA REFUND"), (480, "499.00 Cr")],
            [(40, "18/10/2026 19:32"), (120, "NETFLIX.COM MUMBAI"), (400, "6"), (480, "649.00")],
            [(40, "21/10/2026"), (120, "LATE PAYMENT FEE"), (480, "500.00")],
            [(40, "21/10/2026"), (120, "IGST ON LATE PAYMENT FEE"), (480, "90.00")],
            [(40, "Reward Points Summary"), (300, "Points earned 55")],
            [(40, "Opening Balance 0.00"), (200, "Closing Balance 6,148.00")]]
    page("card_hdfc.pdf", rows, encrypt="ASHA0503")


def card_axis():
    """Layout copied from a real Axis Bank ACE statement; details invented."""
    rows = [[(200, "Axis Bank ACE Credit Card Statement")], [(40, "A CARDHOLDER")],
            [(200, "PAYMENT SUMMARY")],
            [(40, "Total Payment Due"), (140, "Minimum Payment Due"), (240, "Statement Period"), (340, "Payment Due Date"), (440, "Statement Generation Date")],
            [(40, "12,345.00 Dr"), (140, "12,345.00 Dr"), (240, "03/09/2026 - 01/10/2026"), (340, "21/10/2026"), (440, "01/10/2026")],
            [(40, "Credit Card Number"), (140, "Credit Limit"), (240, "Available Credit Limit"), (340, "Available Cash Limit")],
            [(40, "400000******1111"), (140, "1,00,000.00"), (240, "80,000.00"), (340, "20,000.00")],
            [(40, "Previous Balance - Payments - Credits + Purchase + Cash Advance + Other Debit&Charges =Total Payment Due")],
            [(40, "20,000.00 Dr"), (110, "20,000.00"), (170, "300.00"), (230, "12,000.00"), (290, "0.00"), (350, "645.00"), (420, "12,345.00 Dr")],
            [(200, "Account Summary")],
            [(40, "DATE"), (100, "TRANSACTION DETAILS"), (330, "MERCHANT CATEGORY"), (430, "AMOUNT (Rs.)"), (500, "CASHBACK EARNED")],
            [(40, "Card No:"), (100, "400000******1111"), (330, "Name A CARDHOLDER")],
            [(40, "18/09/2026"), (100, "EMI INTEREST - 1/3, REF# 11111111"), (330, "ELECTRONICS"), (430, "550.00 Dr"), (500, "0.00 Cr")],
            [(40, "18/09/2026"), (100, "GST"), (430, "99.00 Dr"), (500, "0.00 Cr")],
            [(40, "18/09/2026"), (100, "EMI PRINCIPAL - 1/3, REF# 11111111"), (330, "ELECTRONICS"), (430, "12,000.00 Dr"), (500, "0.00 Cr")],
            [(40, "22/09/2026"), (100, "SWIGGY BANGALORE"), (330, "FOOD"), (430, "450.00 Dr"), (500, "18.00 Cr")],
            [(40, "20/09/2026"), (100, "BBPS PAYMENT RECEIVED - XX0000000000000001"), (430, "15,000.00 Cr"), (500, "0.00 Dr")],
            [(40, "20/09/2026"), (100, "BBPS PAYMENT RECEIVED - XX0000000000000002"), (430, "5,000.00 Cr"), (500, "0.00 Dr")],
            [(40, "27/09/2026"), (100, "CASHBACK CREDIT SEP26-UTILITY:50~OTHERS:250"), (430, "300.00 Cr"), (500, "0.00 Dr")],
            [(200, "**** End of Statement ****")],
            [(40, "EMI BALANCES")], [(100, "SOME ELECTRONICS"), (330, "11111111"), (430, "24,000.00"), (500, "0.00")]]
    page("card_axis.pdf", rows, encrypt="TEST1234")


def bank():
    rows = [[(40, "State Bank of India")], [(40, "Statement of Account")],
            [(40, "Account Number XXXXXXX1234")], [(40, "Opening Balance"), (200, "50,000.00")],
            [(40, "Txn Date"), (100, "Value Date"), (160, "Description"), (380, "Debit"), (440, "Credit"), (500, "Balance")],
            [(40, "05/10/2026"), (100, "05/10/2026"), (160, "UPI/DR/427700001111/ZEPTO"), (380, "812.00"), (500, "49,188.00")],
            [(160, "MARKETPLACE/YESB/zepto@ybl/order")],
            [(40, "06/10/2026"), (100, "06/10/2026"), (160, "UPI/CR/427700002222/RAVI KUMAR"), (440, "750.00"), (500, "49,938.00")],
            [(160, "/HDFC/ravi@okhdfc/dinner")],
            [(40, "09/10/2026"), (100, "09/10/2026"), (160, "ATM WDL ATM CASH 1234 HYDERABAD"), (380, "2,000.00"), (500, "47,938.00")],
            [(40, "14/10/2026"), (100, "14/10/2026"), (160, "NEFT CR SALARY ONEBEAT"), (440, "92,000.00"), (500, "1,39,938.00")],
            [(40, "Closing Balance"), (200, "1,39,938.00")]]
    page("bank_sbi.pdf", rows)


def scanned():
    c = canvas.Canvas(str(OUT / "scanned.pdf"), pagesize=A4)
    c.rect(50, 500, 400, 200, fill=1)
    c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    phonepe(); bhim(); gpay(); card(); card_axis(); bank(); scanned()
    print("written to", OUT)
