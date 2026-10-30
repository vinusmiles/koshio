import { candidatePasswords } from "./pdfPasswords";

describe("candidatePasswords", () => {
  const asha = { name: "Asha Rani Verma", dob: "1990-03-05" };
  it("builds the bank patterns from name, date of birth and card digits", () => {
    const c = candidatePasswords(asha, ["1111", "2222", null]);
    expect(c[0]).toBe("ASHA0503");               // Axis, HDFC
    expect(c).toContain("asha0503");             // lower-case variant
    expect(c).toContain("050319901111");         // SBI Card: DDMMYYYY + last 4 of that card
    expect(c).toContain("050319902222");
    expect(c).toContain("05031990");
    expect(new Set(c).size).toBe(c.length);
  });
  it("uses the whole name when the first name is short", () => {
    expect(candidatePasswords({ name: "Ali Khan", dob: "1985-12-31" }, [])[0]).toBe("ALIK3112");
  });
  it("never sends more than 20", () => {
    const many = Array.from({ length: 40 }, (_, i) => String(1000 + i));
    expect(candidatePasswords(asha, many).length).toBeLessThanOrEqual(20);
  });
});

import { forgetHints, loadHints, needsHintsSetup, saveHints, skipHintsSetup } from "./pdfPasswords";
describe("opening step", () => {
  beforeEach(() => localStorage.clear());
  it("shows until details are saved or the step is skipped", () => {
    expect(needsHintsSetup()).toBe(true);
    saveHints({ name: " Asha Verma ", dob: "1990-03-05" });
    expect(loadHints()).toEqual({ name: "Asha Verma", dob: "1990-03-05" });
    expect(needsHintsSetup()).toBe(false);
    forgetHints();
    expect(needsHintsSetup()).toBe(true);
    skipHintsSetup();
    expect(needsHintsSetup()).toBe(false);
  });
});
