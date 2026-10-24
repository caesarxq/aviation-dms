import { useMemo } from "react";

export type FieldValidationRule<T> = {
  required?: boolean | string;
  minLength?: number | string;
  min?: number | string;
  max?: number | string;
  pattern?: RegExp | string;
  custom?: (value: any, values: T) => string | undefined;
  message?: string;
};

export type ValidationRules<T> = Partial<Record<keyof T, FieldValidationRule<T>>>;

export type ValidationErrors<T> = Partial<Record<keyof T, string>>;

export function validateField<T extends Record<string, any>>(
  field: keyof T,
  value: any,
  values: T,
  rules: ValidationRules<T> = {}
): string | undefined {
  const rule = rules[field];
  if (!rule) return undefined;

  if (rule.required && (value === undefined || value === null || String(value).trim() === "")) {
    return typeof rule.required === "string" ? rule.required : "This field is required.";
  }

  if (rule.minLength !== undefined && String(value).trim().length < Number(rule.minLength)) {
    return `Must be at least ${rule.minLength} characters.`;
  }

  if (rule.min !== undefined && Number(value) < Number(rule.min)) {
    return `Must be at least ${rule.min}.`;
  }

  if (rule.max !== undefined && Number(value) > Number(rule.max)) {
    return `Must be no more than ${rule.max}.`;
  }

  if (rule.pattern) {
    const regex = typeof rule.pattern === "string" ? new RegExp(rule.pattern) : rule.pattern;
    if (!regex.test(String(value))) {
      return rule.message || "Invalid format.";
    }
  }

  if (rule.custom) {
    return rule.custom(value, values);
  }

  return undefined;
}

export function validateValues<T extends Record<string, any>>(values: T, rules: ValidationRules<T>): ValidationErrors<T> {
  const errors: ValidationErrors<T> = {};
  for (const key of Object.keys(values) as (keyof T)[]) {
    const error = validateField(key, values[key], values, rules);
    if (error) errors[key] = error;
  }
  return errors;
}

export function useValidation<T extends Record<string, any>>(values: T, rules: ValidationRules<T>) {
  const errors = useMemo(() => validateValues(values, rules), [values, rules]);
  const isValid = Object.keys(errors).length === 0;
  return { errors, isValid };
}
