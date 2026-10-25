import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { validateField, validateValues, useValidation } from "./validation";

type AnyRecord = Record<string, any>;

describe("validateField", () => {
  const field = (name: string) => name as any;

  it("returns undefined when no rule matches the field", () => {
    expect(// @ts-expect-error
  validateField(field("name"), "x", {}, {})).toBeUndefined();
  });

  it("rejects undefined with default required message", () => {
    expect(// @ts-expect-error
  validateField(field("email"), undefined, {}, { email: { required: true } })).toBe(
      "This field is required.",
    );
  });

  it("rejects null with default required message", () => {
    expect(// @ts-expect-error
  validateField(field("email"), null, {}, { email: { required: true } })).toBe(
      "This field is required.",
    );
  });

  it("rejects empty string after trim with default required message", () => {
    expect(// @ts-expect-error
  validateField(field("email"), "   ", {}, { email: { required: true } })).toBe(
      "This field is required.",
    );
  });

  it("rejects empty string with custom required message", () => {
    expect(// @ts-expect-error
  validateField(field("email"), "", {}, { email: { required: "Email is mandatory" } })).toBe(
      "Email is mandatory",
    );
  });

  it("accepts non-empty string when required", () => {
    expect(// @ts-expect-error
  validateField(field("email"), "a@b.com", {}, { email: { required: true } })).toBeUndefined();
  });

  it("accepts zero when required", () => {
    expect(// @ts-expect-error
  validateField(field("count"), 0, {}, { count: { required: true } })).toBeUndefined();
  });

  it("accepts false when required", () => {
    expect(// @ts-expect-error
  validateField(field("flag"), false, {}, { flag: { required: true } })).toBeUndefined();
  });

  it("enforces minLength on string values", () => {
    expect(// @ts-expect-error
  validateField(field("name"), "ab", {}, { name: { minLength: 3 } })).toBe(
      "Must be at least 3 characters.",
    );
  });

  it("accepts value at exact minLength", () => {
    expect(// @ts-expect-error
  validateField(field("name"), "abc", {}, { name: { minLength: 3 } })).toBeUndefined();
  });

  it("ignores minLength when undefined", () => {
    expect(// @ts-expect-error
  validateField(field("name"), "a", {}, { name: { minLength: undefined } })).toBeUndefined();
  });

  it("enforces minLength using trimmed length", () => {
    expect(// @ts-expect-error
  validateField(field("name"), "a ", {}, { name: { minLength: 2 } })).toBe(
      "Must be at least 2 characters.",
    );
  });

  it("ignores minLength when set to 0", () => {
    expect(// @ts-expect-error
  validateField(field("name"), "a", {}, { name: { minLength: 0 } })).toBeUndefined();
  });

  it("enforces numeric min", () => {
    expect(// @ts-expect-error
  validateField(field("age"), 17, {}, { age: { min: 18 } })).toBe("Must be at least 18.");
  });

  it("ignores min when set to 0", () => {
    expect(// @ts-expect-error
  validateField(field("age"), -1, {}, { age: { min: 0 } })).toBe("Must be at least 0.");
  });

  it("ignores min when undefined", () => {
    expect(// @ts-expect-error
  validateField(field("age"), -1, {}, { age: { min: undefined } })).toBeUndefined();
  });

  it("accepts value at exact min", () => {
    expect(// @ts-expect-error
  validateField(field("age"), 18, {}, { age: { min: 18 } })).toBeUndefined();
  });

  it("enforces numeric max", () => {
    expect(// @ts-expect-error
  validateField(field("age"), 101, {}, { age: { max: 100 } })).toBe("Must be no more than 100.");
  });

  it("ignores max when set to 0", () => {
    expect(// @ts-expect-error
  validateField(field("age"), 1, {}, { age: { max: 0 } })).toBe("Must be no more than 0.");
  });

  it("ignores max when undefined", () => {
    expect(// @ts-expect-error
  validateField(field("age"), 1, {}, { age: { max: undefined } })).toBeUndefined();
  });

  it("accepts value at exact max", () => {
    expect(// @ts-expect-error
  validateField(field("age"), 100, {}, { age: { max: 100 } })).toBeUndefined();
  });

  it("accepts value below max", () => {
    expect(// @ts-expect-error
  validateField(field("age"), 50, {}, { age: { max: 100 } })).toBeUndefined();
  });

  it("validates pattern as RegExp", () => {
    expect(// @ts-expect-error
  validateField(field("code"), "abc", {}, { code: { pattern: /^[A-Z]+$/ } })).toBe(
      "Invalid format.",
    );
  });

  it("accepts value matching RegExp pattern", () => {
    expect(// @ts-expect-error
  validateField(field("code"), "ABC", {}, { code: { pattern: /^[A-Z]+$/ } })).toBeUndefined();
  });

  it("validates pattern as string", () => {
    expect(// @ts-expect-error
  validateField(field("code"), "abc", {}, { code: { pattern: "^[A-Z]+$" } })).toBe(
      "Invalid format.",
    );
  });

  it("uses custom message on pattern failure", () => {
    expect(
      // @ts-expect-error
  validateField(field("code"), "abc", {}, { code: { pattern: /^[A-Z]+$/, message: "Uppercase only" } }),
    ).toBe("Uppercase only");
  });

  it("runs custom validator and returns its message", () => {
    expect(
      // @ts-expect-error
  validateField(field("x"), "bad", {}, {
        x: { custom: (v: any) => (v === "bad" ? "no bad" : undefined) },
      }),
    ).toBe("no bad");
  });

  it("accepts when custom validator returns undefined", () => {
    expect(
      // @ts-expect-error
  validateField(field("x"), "ok", {}, {
        x: { custom: (v: any) => (v === "bad" ? "no bad" : undefined) },
      }),
    ).toBeUndefined();
  });

  it("runs custom validator with full values object", () => {
    let receivedValues: AnyRecord | undefined;
  validateField(field("x"), "v", { x: "v", y: 1 } as AnyRecord, {
      x: { custom: (_: any, values: AnyRecord) => { receivedValues = values; return undefined; } },
    });
    expect(receivedValues).toEqual({ x: "v", y: 1 });
  });

  it("converts non-string values to string for minLength", () => {
    expect(// @ts-expect-error
  validateField(field("num"), 123, {}, { num: { minLength: 4 } })).toBe(
      "Must be at least 4 characters.",
    );
  });

  it("converts non-string values to string for pattern", () => {
    expect(// @ts-expect-error
  validateField(field("num"), 123, {}, { num: { pattern: /^[A-Z]+$/ } })).toBe(
      "Invalid format.",
    );
  });

  it("skips minLength when rule is undefined", () => {
    expect(// @ts-expect-error
  validateField(field("name"), "a", {}, { name: {} })).toBeUndefined();
  });
});

describe("validateValues", () => {
  it("returns empty object when all fields are valid", () => {
    expect(validateValues({ a: "1", b: "2" }, { a: { required: true }, b: { required: true } })).toEqual({});
  });

  it("collects errors from multiple fields", () => {
    const errors = validateValues(
      { a: "", b: "x" },
      { a: { required: true }, b: { minLength: 5 } },
    );
    expect(errors).toEqual({ a: "This field is required.", b: "Must be at least 5 characters." });
  });

  it("returns empty object when rules object is empty", () => {
    expect(validateValues({ a: "1" }, {})).toEqual({});
  });

  it("ignores fields without rules", () => {
    expect(validateValues({ a: "1", b: "" }, { a: { required: true } })).toEqual({});
  });

  it("returns only the first failing rule per field", () => {
    const errors = validateValues({ age: 10 }, { age: { required: true, min: 18 } });
    expect(Object.keys(errors)).toHaveLength(1);
  });
});

describe("useValidation", () => {
  it("returns empty errors and isValid true for valid input", () => {
    const { result } = renderHook(() => useValidation({ email: "a@b.com" }, {
      email: { required: true, pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/ },
    }));
    expect(result.current.errors).toEqual({});
    expect(result.current.isValid).toBe(true);
  });

  it("returns errors and isValid false for invalid input", () => {
    const { result } = renderHook(() => useValidation({ email: "bad" }, {
      email: { required: true, pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/ },
    }));
    expect(result.current.errors).toEqual({ email: "Invalid format." });
    expect(result.current.isValid).toBe(false);
  });

  it("recomputes when values change", () => {
    const { result, rerender } = renderHook((props) => useValidation(props.values, { name: { required: true } }), {
      initialProps: { values: { name: "" } },
    });
    expect(result.current.errors).toEqual({ name: "This field is required." });
    rerender({ values: { name: "x" } });
    expect(result.current.errors).toEqual({});
  });

  it("recomputes when rules change", () => {
    const { result, rerender } = renderHook((props) => useValidation(props.values, props.rules), {
      initialProps: {
        values: { age: 17 },
        rules: { age: { min: 18 } },
      },
    });
    expect(result.current.errors).toEqual({ age: "Must be at least 18." });
    rerender({
      values: { age: 17 },
      rules: { age: { min: 10 } },
    });
    expect(result.current.errors).toEqual({});
  });
});
