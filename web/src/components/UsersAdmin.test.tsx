/**
 * Tests for <UsersAdmin> (admin user management, FR-14).
 *
 * They verify the user list renders and that changing a role calls the API. The
 * `api` module is mocked so list/role calls are controlled and assertable.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { UsersAdmin } from "./UsersAdmin";
import type { UserRow } from "../types";

const listUsers = vi.fn();
const setUserRole = vi.fn();
vi.mock("../api", () => ({
  api: {
    listUsers: (...a: unknown[]) => listUsers(...a),
    setUserRole: (...a: unknown[]) => setUserRole(...a),
  },
  ApiError: class ApiError extends Error {},
}));

const tech: UserRow = {
  id: "u1",
  name: "Dana Tech",
  email: "dana@example.com",
  role: "tech",
  created_at: "2026-06-16T00:00:00Z",
};

describe("UsersAdmin", () => {
  beforeEach(() => vi.clearAllMocks());

  it("promotes a user by changing the role select", async () => {
    listUsers.mockResolvedValue([tech]);
    setUserRole.mockResolvedValue({ ...tech, role: "curator" });
    render(<UsersAdmin />);

    const select = await screen.findByLabelText(/role for dana tech/i);
    await userEvent.selectOptions(select, "curator");

    await waitFor(() => expect(setUserRole).toHaveBeenCalledWith("u1", "curator"));
    expect((select as HTMLSelectElement).value).toBe("curator");
  });
});
