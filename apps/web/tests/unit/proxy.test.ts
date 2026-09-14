import { describe, expect, test } from "bun:test";
import proxy from "../../proxy";
import { NextRequest } from "next/server";

describe("Proxy & Routing Verification (proxy.ts)", () => {
  const BASE_URL = "http://localhost:3000";

  function createRequest(
    pathname: string,
    options: {
      search?: string;
      host?: string;
      cookies?: Record<string, string>;
      headers?: Record<string, string>;
    } = {}
  ) {
    const url = new URL(pathname + (options.search || ""), options.host ? `http://${options.host}` : BASE_URL);
    const headers = new Headers(options.headers || {});
    if (options.host) {
      headers.set("host", options.host);
    } else {
      headers.set("host", "localhost:3000");
    }

    const cookieStrings: string[] = [];
    if (options.cookies) {
      for (const [key, value] of Object.entries(options.cookies)) {
        cookieStrings.push(`${key}=${value}`);
      }
      headers.set("cookie", cookieStrings.join("; "));
    }

    const req = new NextRequest(url, { headers });
    return req;
  }

  describe("1. Single-tenancy role-portal redirects (§0b)", () => {
    test("STUDENT with active session hitting '/' redirects to '/my-school'", async () => {
      const req = createRequest("/", {
        cookies: {
          LH_session: "valid-session-token",
          LH_role: "STUDENT",
        },
      });

      const res = await proxy(req);
      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toBe(`${BASE_URL}/my-school`);
    });

    test("PARENT with active session hitting '/' redirects to '/my-school'", async () => {
      const req = createRequest("/", {
        cookies: {
          LH_session: "valid-session-token",
          LH_role: "PARENT",
        },
      });

      const res = await proxy(req);
      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toBe(`${BASE_URL}/my-school`);
    });

    test("TEACHER with active session hitting '/' redirects to '/dash'", async () => {
      const req = createRequest("/", {
        cookies: {
          LH_session: "valid-session-token",
          LH_role: "TEACHER",
        },
      });

      const res = await proxy(req);
      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toBe(`${BASE_URL}/dash`);
    });

    test("ADMIN with active session hitting '/' redirects to '/dash'", async () => {
      const req = createRequest("/", {
        cookies: {
          LH_session: "valid-session-token",
          LH_role: "ADMIN",
        },
      });

      const res = await proxy(req);
      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toBe(`${BASE_URL}/dash`);
    });

    test("STUDENT with session on '/home' redirects to '/my-school'", async () => {
      const req = createRequest("/home", {
        cookies: {
          LH_session: "valid-session-token",
          LH_role: "STUDENT",
        },
      });

      const res = await proxy(req);
      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toBe(`${BASE_URL}/my-school`);
    });

    test("ADMIN with session on '/login' redirects to '/dash'", async () => {
      const req = createRequest("/login", {
        cookies: {
          LH_session: "valid-session-token",
          LH_role: "ADMIN",
        },
      });

      const res = await proxy(req);
      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toBe(`${BASE_URL}/dash`);
    });

    test("Unauthenticated user on '/' falls through without role redirect", async () => {
      const req = createRequest("/");
      const res = await proxy(req);
      // In single-tenancy OSS fallback, rewritten to /orgs/default/
      expect(res.headers.get("x-middleware-rewrite")).toContain("/orgs/default/");
    });
  });

  describe("2. Standalone direct route passthroughs (§5b)", () => {
    test("/student course player passes through directly", async () => {
      const req = createRequest("/student/course-123/lesson-456");
      const res = await proxy(req);
      expect(res.headers.get("x-middleware-rewrite")).toBe(`${BASE_URL}/student/course-123/lesson-456`);
    });

    test("/live standalone video room passes through directly", async () => {
      const req = createRequest("/live/room-algebra-101");
      const res = await proxy(req);
      expect(res.headers.get("x-middleware-rewrite")).toBe(`${BASE_URL}/live/room-algebra-101`);
    });
  });

  describe("3. SMS dashboard and learner route rewrites to tenant catch-all (§11)", () => {
    const smsRoutes = [
      { name: "SMS dashboard root", path: "/dash", expected: "/orgs/default/dash" },
      { name: "Roles settings", path: "/dash/school-settings/roles", expected: "/orgs/default/dash/school-settings/roles" },
      { name: "Discipline module", path: "/dash/discipline", expected: "/orgs/default/dash/discipline" },
      { name: "Alumni module", path: "/dash/alumni", expected: "/orgs/default/dash/alumni" },
      { name: "Certificates manager", path: "/dash/certificates-manager", expected: "/orgs/default/dash/certificates-manager" },
      { name: "Gamification module", path: "/dash/gamification", expected: "/orgs/default/dash/gamification" },
      { name: "Facilities module", path: "/dash/facilities", expected: "/orgs/default/dash/facilities" },
      { name: "Pathways module", path: "/dash/pathways", expected: "/orgs/default/dash/pathways" },
      { name: "Live classes index", path: "/dash/live-classes", expected: "/orgs/default/dash/live-classes" },
      { name: "Live class room session", path: "/dash/live-classes/101", expected: "/orgs/default/dash/live-classes/101" },
      { name: "Learner portal root", path: "/my-school", expected: "/orgs/default/my-school" },
      { name: "Learner overview", path: "/my-school/overview", expected: "/orgs/default/my-school/overview" },
      { name: "Learner academics", path: "/my-school/academics", expected: "/orgs/default/my-school/academics" },
      { name: "Learner attendance", path: "/my-school/attendance", expected: "/orgs/default/my-school/attendance" },
      { name: "Public certificates", path: "/certificates", expected: "/orgs/default/certificates" },
    ];

    for (const { name, path, expected } of smsRoutes) {
      test(`properly rewrites ${name} (${path}) to ${expected}`, async () => {
        const req = createRequest(path);
        const res = await proxy(req);
        expect(res.headers.get("x-middleware-rewrite")).toBe(`${BASE_URL}${expected}`);
      });
    }

    test("preserves query parameters on tenant rewrite", async () => {
      const req = createRequest("/dash/school-settings/roles", { search: "?tab=permissions&page=2" });
      const res = await proxy(req);
      expect(res.headers.get("x-middleware-rewrite")).toBe(
        `${BASE_URL}/orgs/default/dash/school-settings/roles?tab=permissions&page=2`
      );
    });
  });

  describe("4. Auth routes (§3 & §4)", () => {
    test("/login rewrites to /auth/login for unauthenticated visitor", async () => {
      const req = createRequest("/login");
      const res = await proxy(req);
      expect(res.headers.get("x-middleware-rewrite")).toBe(`${BASE_URL}/auth/login`);
    });

    test("/signup rewrites to /auth/signup", async () => {
      const req = createRequest("/signup");
      const res = await proxy(req);
      expect(res.headers.get("x-middleware-rewrite")).toBe(`${BASE_URL}/auth/signup`);
    });

    test("/auth/callback/oauth passes through directly", async () => {
      const req = createRequest("/auth/callback/oauth");
      const res = await proxy(req);
      expect(res.headers.get("x-middleware-rewrite")).toBe(`${BASE_URL}/auth/callback/oauth`);
    });

    test("/auth/magic passes through directly", async () => {
      const req = createRequest("/auth/magic", { search: "?token=xyz" });
      const res = await proxy(req);
      expect(res.headers.get("x-middleware-rewrite")).toBe(`${BASE_URL}/auth/magic?token=xyz`);
    });
  });

  describe("5. Case canonicalization", () => {
    test("/Login 308 redirects to /login", async () => {
      const req = createRequest("/Login");
      const res = await proxy(req);
      expect(res.status).toBe(308);
      expect(res.headers.get("location")).toBe(`${BASE_URL}/login`);
    });
  });
});
