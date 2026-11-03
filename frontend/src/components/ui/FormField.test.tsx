import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import FormField from "./FormField";

describe("FormField accessibility", () => {
  it("associates hint and existing error descriptions with the control", () => {
    render(
      <FormField htmlFor="audit-scope" label="Audit scope" hint="Identify the departments covered.">
        <input id="audit-scope" aria-describedby="audit-scope-error" />
        <p id="audit-scope-error">Scope is required.</p>
      </FormField>,
    );

    expect(screen.getByLabelText("Audit scope")).toHaveAttribute("aria-describedby", "audit-scope-hint audit-scope-error");
  });
});
