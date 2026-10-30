import { formatDate, formatINR, formatMonth, parseAmount } from "./format";

describe("formatINR", () => {
  it("uses Indian digit grouping", () => {
    expect(formatINR("125000")).toBe("₹1,25,000.00");
    expect(formatINR("12345678.5")).toBe("₹1,23,45,678.50");
    expect(formatINR(125000, { whole: true })).toBe("₹1,25,000");
  });
  it("shows negatives with a minus sign in front of the rupee", () => {
    expect(formatINR("-500")).toBe("−₹500.00");
  });
  it("handles empty values", () => {
    expect(formatINR(null)).toBe("₹0.00");
    expect(formatINR("abc")).toBe("—");
  });
});

describe("dates", () => {
  it("formats as DD MMM YYYY without timezone shifts", () => {
    expect(formatDate("2026-10-05")).toBe("05 Oct 2026");
    expect(formatDate("2026-01-01T00:00:00Z")).toBe("01 Jan 2026");
  });
  it("formats chart months", () => expect(formatMonth("2026-04")).toBe("Apr 26"));
});

describe("parseAmount", () => {
  it("accepts common ways of typing rupees", () => {
    expect(parseAmount("1,250.5")).toBe("1250.50");
    expect(parseAmount("₹ 1250")).toBe("1250.00");
  });
  it("rejects zero, negatives, words and extra decimals", () => {
    for (const bad of ["0", "-5", "abc", "10.005", ""]) expect(parseAmount(bad)).toBeNull();
  });
});

import { shortFunding } from "./format";
describe("shortFunding", () => {
  it("shortens what paid for a UPI payment", () => {
    expect(shortFunding("AXIS BANK RUPAY CREDIT CARD 652111XXXXXXXX77")).toBe("Axis card ••77");
    expect(shortFunding("653000XXXXXXXX19")).toBe("card ••19");
    expect(shortFunding("Axis Bank Ltd. XXXX123456")).toBe("Axis a/c ••3456");
    expect(shortFunding("HDFC BANK LTD ******9999")).toBe("Hdfc a/c ••9999");
    expect(shortFunding("XXXXXXXXXX13")).toBe("a/c ••13");
    expect(shortFunding("UPI Lite")).toBe("UPI Lite");
    expect(shortFunding(null)).toBeNull();
  });
});
