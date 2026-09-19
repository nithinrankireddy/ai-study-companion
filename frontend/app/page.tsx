"use client";

import { useEffect, useState } from "react";

const API = "http://localhost:8000";

type Space = {
  id: string;
  name: string;
  description: string;
};

type User = {
  id?: string;
  name?: string;
  email?: string;
  role?: string;
};

export default function Home() {
  const [isLogin, setIsLogin] = useState(true);
  const [loggedIn, setLoggedIn] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [spaces, setSpaces] = useState<Space[]>([]);
  const [spaceName, setSpaceName] = useState("");
  const [spaceDescription, setSpaceDescription] = useState("");
  const [message, setMessage] = useState("");

  const [checkingAuth, setCheckingAuth] = useState(true);

  // ============================================================
  // CHECK EXISTING LOGIN
  // ============================================================

  useEffect(() => {
    const checkExistingLogin = async () => {
      const token = localStorage.getItem("token");
      const savedUser = localStorage.getItem("user");

      if (!token) {
        setCheckingAuth(false);
        return;
      }

      let user: User | null = null;

      try {
        user = savedUser ? JSON.parse(savedUser) : null;
      } catch {
        user = null;
      }

      // If saved user is admin, go directly to admin dashboard
      if (user?.role === "admin") {
        window.location.href = "/admin";
        return;
      }

      // If role isn't available, verify through admin endpoint.
      // Admin gets 200, normal user gets 403.
      try {
        const adminCheck = await fetch(`${API}/admin/overview`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (adminCheck.ok) {
          window.location.href = "/admin";
          return;
        }
      } catch {
        // Ignore and continue as normal user
      }

      setLoggedIn(true);
      await loadSpaces(token);
      setCheckingAuth(false);
    };

    checkExistingLogin();
  }, []);

  // ============================================================
  // LOAD SPACES
  // ============================================================

  const loadSpaces = async (token: string) => {
    try {
      const response = await fetch(`${API}/workspace/spaces`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setSpaces(await response.json());
      } else if (response.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setLoggedIn(false);
      }
    } catch (error) {
      console.error("Failed to load spaces:", error);
    }
  };

  // ============================================================
  // LOGIN / SIGNUP
  // ============================================================

  const handleAuth = async () => {
    setMessage("");

    if (!email.trim() || !password.trim()) {
      setMessage("Please enter email and password.");
      return;
    }

    if (!isLogin && !name.trim()) {
      setMessage("Please enter your name.");
      return;
    }

    const endpoint = isLogin
      ? "/auth/login"
      : "/auth/signup";

    const body = isLogin
      ? {
          email: email.trim(),
          password,
        }
      : {
          name: name.trim(),
          email: email.trim(),
          password,
        };

    try {
      const response = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        setMessage(
          data.detail ||
            data.message ||
            "Authentication failed"
        );
        return;
      }

      const token = data.access_token;

      if (!token) {
        setMessage("Authentication succeeded but no token was returned.");
        return;
      }

      localStorage.setItem("token", token);

      if (data.user) {
        localStorage.setItem(
          "user",
          JSON.stringify(data.user)
        );
      }

      // ========================================================
      // ROLE-BASED REDIRECT
      // ========================================================

      const userRole = data.user?.role;

      if (userRole === "admin") {
        window.location.href = "/admin";
        return;
      }

      // Fallback role check for older auth responses
      // that may not include role in data.user.
      try {
        const adminCheck = await fetch(
          `${API}/admin/overview`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (adminCheck.ok) {
          window.location.href = "/admin";
          return;
        }
      } catch {
        // Continue as normal user
      }

      // ========================================================
      // NORMAL USER
      // ========================================================

      setLoggedIn(true);
      setMessage("");

      await loadSpaces(token);
    } catch (error) {
      console.error("Authentication error:", error);
      setMessage("Backend connection failed");
    }
  };

  // ============================================================
  // CREATE SPACE
  // ============================================================

  const createSpace = async () => {
    const token = localStorage.getItem("token");

    if (!token || !spaceName.trim()) {
      return;
    }

    try {
      const response = await fetch(
        `${API}/workspace/spaces`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            name: spaceName.trim(),
            description: spaceDescription.trim(),
          }),
        }
      );

      if (response.ok) {
        const newSpace = await response.json();

        setSpaces((prev) => [
          ...prev,
          newSpace,
        ]);

        setSpaceName("");
        setSpaceDescription("");
      } else {
        const data = await response.json();

        setMessage(
          data.detail ||
            "Failed to create space"
        );
      }
    } catch (error) {
      console.error(
        "Create space error:",
        error
      );

      setMessage(
        "Unable to create space"
      );
    }
  };

  // ============================================================
  // LOGOUT
  // ============================================================

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("selectedSpace");

    setLoggedIn(false);
    setSpaces([]);
    setName("");
    setEmail("");
    setPassword("");
  };

  // ============================================================
  // AUTH CHECK LOADING
  // ============================================================

  if (checkingAuth) {
    return (
      <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-3xl mb-3">
            📚
          </div>

          <p className="text-slate-400">
            Loading AI Study Companion...
          </p>
        </div>
      </main>
    );
  }

  // ============================================================
  // LOGIN / SIGNUP SCREEN
  // ============================================================

  if (!loggedIn) {
    return (
      <main className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">

          <h1 className="text-3xl font-bold text-slate-900 text-center">
            AI Study Companion
          </h1>

          <p className="text-center text-slate-500 mt-2">
            Your AI-powered learning workspace
          </p>

          {/* LOGIN / SIGNUP TABS */}

          <div className="flex mt-8 border-b">
            <button
              onClick={() => {
                setIsLogin(true);
                setMessage("");
              }}
              className={`flex-1 pb-3 font-semibold ${
                isLogin
                  ? "border-b-2 border-blue-600 text-blue-600"
                  : "text-slate-400"
              }`}
            >
              Login
            </button>

            <button
              onClick={() => {
                setIsLogin(false);
                setMessage("");
              }}
              className={`flex-1 pb-3 font-semibold ${
                !isLogin
                  ? "border-b-2 border-blue-600 text-blue-600"
                  : "text-slate-400"
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* FORM */}

          <div className="mt-6 space-y-4">

            {!isLogin && (
              <input
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) =>
                  setName(e.target.value)
                }
                className="w-full rounded-lg border p-3 text-slate-900"
              />
            )}

            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
              className="w-full rounded-lg border p-3 text-slate-900"
            />

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) =>
                setPassword(e.target.value)
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleAuth();
                }
              }}
              className="w-full rounded-lg border p-3 text-slate-900"
            />

            <button
              onClick={handleAuth}
              className="w-full rounded-lg bg-blue-600 py-3 font-semibold text-white hover:bg-blue-700 transition"
            >
              {isLogin
                ? "Login"
                : "Create Account"}
            </button>

            {message && (
              <p className="text-center text-sm text-red-500">
                {message}
              </p>
            )}

          </div>
        </div>
      </main>
    );
  }

  // ============================================================
  // NORMAL USER HOME
  // ============================================================

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* HEADER */}

      <header className="border-b border-slate-800 p-5 flex justify-between items-center">

        <div>
          <h1 className="text-2xl font-bold">
            AI Study Companion
          </h1>

          <p className="text-slate-400">
            Your Learning Workspace
          </p>
        </div>

        <button
          onClick={logout}
          className="rounded-lg bg-red-600 px-4 py-2 hover:bg-red-700 transition"
        >
          Logout
        </button>

      </header>

      {/* CONTENT */}

      <section className="max-w-6xl mx-auto p-8">

        <h2 className="text-3xl font-bold">
          Your Spaces
        </h2>

        <p className="text-slate-400 mt-2">
          Organize your learning into focused areas.
        </p>

        {/* CREATE SPACE */}

        <div className="mt-8 rounded-2xl bg-slate-900 p-6">

          <h3 className="text-xl font-semibold">
            Create Space
          </h3>

          <div className="grid gap-3 mt-4">

            <input
              placeholder="Space name"
              value={spaceName}
              onChange={(e) =>
                setSpaceName(e.target.value)
              }
              className="rounded-lg bg-slate-800 border border-slate-700 p-3"
            />

            <input
              placeholder="Description"
              value={spaceDescription}
              onChange={(e) =>
                setSpaceDescription(
                  e.target.value
                )
              }
              className="rounded-lg bg-slate-800 border border-slate-700 p-3"
            />

            <button
              onClick={createSpace}
              className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-700 transition"
            >
              + Create Space
            </button>

          </div>

          {message && (
            <p className="text-red-400 text-sm mt-3">
              {message}
            </p>
          )}

        </div>

        {/* SPACES */}

        <div className="grid md:grid-cols-3 gap-5 mt-8">

          {spaces.map((space) => (
            <div
              key={space.id}
              className="rounded-2xl bg-slate-900 border border-slate-800 p-6"
            >

              <h3 className="text-xl font-bold">
                {space.name}
              </h3>

              <p className="text-slate-400 mt-2">
                {space.description ||
                  "No description"}
              </p>

              <button
                onClick={() => {
                  localStorage.setItem(
                    "selectedSpace",
                    JSON.stringify(space)
                  );

                  window.location.href =
                    `/space/${space.id}`;
                }}
                className="mt-5 text-blue-400 hover:text-blue-300"
              >
                Open Space →
              </button>

            </div>
          ))}

        </div>

        {spaces.length === 0 && (
          <div className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-8 text-center">

            <p className="text-slate-400">
              No learning spaces yet.
            </p>

            <p className="text-sm text-slate-500 mt-2">
              Create your first space above to start learning.
            </p>

          </div>
        )}

      </section>

    </main>
  );
}