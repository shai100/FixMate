import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Console } from "./Console";

// The console mounts ReviewQueue (which calls the API on render); stub the whole
// api module so these tests stay pure and deterministic.
vi.mock("../api", () => ({
  api: {
    reviewQueue: vi.fn().mockResolvedValue([]),
    listDocuments: vi.fn().mockResolvedValue([]),
    listEquipment: vi.fn().mockResolvedValue([]),
    listUsers: vi.fn().mockResolvedValue([]),
  },
  ApiError: class ApiError extends Error {},
}));

describe("Console role guard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("hides the Users tab from curators", () => {
    render(<Console role="curator" />);
    expect(screen.getByRole("button", { name: /review queue/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^users$/i })).not.toBeInTheDocument();
  });

  it("shows the Users tab to admins", () => {
    render(<Console role="admin" />);
    expect(screen.getByRole("button", { name: /^users$/i })).toBeInTheDocument();
  });
});
