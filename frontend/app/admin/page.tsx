"use client";

import { useEffect, useState } from "react";

const API = "http://localhost:8000";

type Overview = {
  users: number;
  spaces: number;
  projects: number;
  materials: number;
  processed_materials: number;
  learning: {
    quiz_attempts: number;
    average_quiz_score: number;
    assessment_attempts: number;
    average_assessment_score: number;
    tutor_questions: number;
  };
  ai: {
    requests: number;
    successes: number;
    failures: number;
    success_rate: number;
    total_tokens: number;
    estimated_cost: number;
    average_latency_ms: number;
  };
};

type AIUsage = {
  feature: string;
  model: string;
  status: string;
  requests: number;
  average_latency_ms: number;
  prompt_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
};

type UserRow = {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
};

type ProjectRow = {
  id: string;
  name: string;
  created_at: string;
  space_name: string;
  owner_email: string;
};

type ActivityRow = {
  id: number;
  project_id: string;
  user_id: string;
  event_type: string;
  metadata: any;
  created_at: string;
};

export default function AdminPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [aiUsage, setAiUsage] = useState<AIUsage[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [activity, setActivity] = useState<ActivityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("selectedSpace");
    window.location.href = "/";
  };

  async function loadAdminData() {
    try {
      setLoading(true);
      setError("");

      const token = localStorage.getItem("token");

      if (!token) {
        throw new Error("Please login first.");
      }

      const headers = {
        Authorization: `Bearer ${token}`,
      };

      const responses = await Promise.all([
        fetch(`${API}/admin/overview`, { headers }),
        fetch(`${API}/admin/ai-usage`, { headers }),
        fetch(`${API}/admin/users`, { headers }),
        fetch(`${API}/admin/projects`, { headers }),
        fetch(`${API}/admin/activity`, { headers }),
      ]);

      if (responses[0].status === 403) {
        throw new Error("Admin access required.");
      }

      if (responses.some((response) => !response.ok)) {
        throw new Error("Failed to load admin dashboard data.");
      }

      const [
        overviewData,
        aiData,
        usersData,
        projectsData,
        activityData,
      ] = await Promise.all(responses.map((response) => response.json()));

      setOverview(overviewData);
      setAiUsage(aiData.ai_usage || []);
      setUsers(usersData.users || []);
      setProjects(projectsData.projects || []);
      setActivity(activityData.activity || []);
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAdminData();
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-2xl font-semibold">
            Loading Admin Dashboard...
          </div>
          <div className="text-slate-400 mt-2">
            Collecting system analytics
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-slate-950 text-white p-8">
        <div className="max-w-3xl mx-auto mt-20 rounded-2xl border border-red-500/30 bg-red-500/10 p-8">
          <h1 className="text-2xl font-bold text-red-300">
            Admin Dashboard
          </h1>
          <p className="mt-3 text-slate-300">{error}</p>

          <button
            onClick={loadAdminData}
            className="mt-6 rounded-lg bg-white px-5 py-2.5 font-medium text-slate-900 hover:bg-slate-200"
          >
            Retry
          </button>
        </div>
      </main>
    );
  }

  if (!overview) return null;

  const cards = [
    ["Users", overview.users],
    ["Spaces", overview.spaces],
    ["Projects", overview.projects],
    ["Materials", overview.materials],
    ["Quiz Attempts", overview.learning.quiz_attempts],
    ["Assessment Attempts", overview.learning.assessment_attempts],
    ["Tutor Questions", overview.learning.tutor_questions],
    ["AI Requests", overview.ai.requests],
  ];

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="max-w-7xl mx-auto px-6 py-8">

        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
          <div>
            <div className="text-sm text-cyan-400 font-medium">
              AI STUDY COMPANION
            </div>
            <h1 className="text-3xl md:text-4xl font-bold mt-1">
              Admin Dashboard
            </h1>
            <p className="text-slate-400 mt-2">
              System, learning and AI usage analytics
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={loadAdminData}
              className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 hover:bg-slate-800"
            >
              Refresh
            </button>

            <button
              onClick={logout}
              className="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white hover:bg-red-700"
            >
              Logout
            </button>
          </div>
        </div>

        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {cards.map(([label, value]) => (
            <div
              key={String(label)}
              className="rounded-2xl border border-slate-800 bg-slate-900 p-5"
            >
              <div className="text-sm text-slate-400">{label}</div>
              <div className="text-3xl font-bold mt-2">
                {Number(value).toLocaleString()}
              </div>
            </div>
          ))}
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold mb-4">
            Learning Analytics
          </h2>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-slate-400">Average Quiz Score</div>
              <div className="text-3xl font-bold mt-2">
                {overview.learning.average_quiz_score.toFixed(1)}%
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-slate-400">
                Average Assessment Score
              </div>
              <div className="text-3xl font-bold mt-2">
                {overview.learning.average_assessment_score.toFixed(1)}%
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-slate-400">Processed Materials</div>
              <div className="text-3xl font-bold mt-2">
                {overview.processed_materials}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold mb-4">
            AI System Analytics
          </h2>

          <div className="grid md:grid-cols-4 gap-4">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-slate-400">Success Rate</div>
              <div className="text-3xl font-bold mt-2">
                {overview.ai.success_rate.toFixed(1)}%
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-slate-400">Failures</div>
              <div className="text-3xl font-bold mt-2">
                {overview.ai.failures}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-slate-400">Total Tokens</div>
              <div className="text-3xl font-bold mt-2">
                {overview.ai.total_tokens.toLocaleString()}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-slate-400">Avg Latency</div>
              <div className="text-3xl font-bold mt-2">
                {overview.ai.average_latency_ms.toFixed(0)} ms
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold mb-4">
            AI Usage by Feature
          </h2>

          <div className="overflow-x-auto rounded-2xl border border-slate-800">
            <table className="w-full text-left">
              <thead className="bg-slate-900 text-slate-400 text-sm">
                <tr>
                  <th className="p-4">Feature</th>
                  <th className="p-4">Model</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Requests</th>
                  <th className="p-4">Tokens</th>
                  <th className="p-4">Latency</th>
                </tr>
              </thead>

              <tbody>
                {aiUsage.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-500">
                      No AI usage recorded yet.
                    </td>
                  </tr>
                ) : (
                  aiUsage.map((item, index) => (
                    <tr
                      key={`${item.feature}-${item.model}-${item.status}-${index}`}
                      className="border-t border-slate-800"
                    >
                      <td className="p-4 font-medium">{item.feature}</td>
                      <td className="p-4 text-slate-400">{item.model}</td>
                      <td className="p-4">
                        <span
                          className={
                            item.status === "success"
                              ? "text-emerald-400"
                              : "text-red-400"
                          }
                        >
                          {item.status}
                        </span>
                      </td>
                      <td className="p-4">
                        {Number(item.requests).toLocaleString()}
                      </td>
                      <td className="p-4">
                        {Number(item.total_tokens).toLocaleString()}
                      </td>
                      <td className="p-4">
                        {Number(item.average_latency_ms).toFixed(0)} ms
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold mb-4">
            Users
          </h2>

          <div className="overflow-x-auto rounded-2xl border border-slate-800">
            <table className="w-full text-left">
              <thead className="bg-slate-900 text-slate-400 text-sm">
                <tr>
                  <th className="p-4">Name</th>
                  <th className="p-4">Email</th>
                  <th className="p-4">Role</th>
                  <th className="p-4">Created</th>
                </tr>
              </thead>

              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-t border-slate-800">
                    <td className="p-4">{user.name || "—"}</td>
                    <td className="p-4 text-slate-400">{user.email}</td>
                    <td className="p-4">
                      <span
                        className={
                          user.role === "admin"
                            ? "text-cyan-400"
                            : "text-slate-300"
                        }
                      >
                        {user.role}
                      </span>
                    </td>
                    <td className="p-4 text-slate-400">
                      {new Date(user.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold mb-4">
            Projects
          </h2>

          <div className="overflow-x-auto rounded-2xl border border-slate-800">
            <table className="w-full text-left">
              <thead className="bg-slate-900 text-slate-400 text-sm">
                <tr>
                  <th className="p-4">Project</th>
                  <th className="p-4">Space</th>
                  <th className="p-4">Owner</th>
                  <th className="p-4">Created</th>
                </tr>
              </thead>

              <tbody>
                {projects.map((project) => (
                  <tr key={project.id} className="border-t border-slate-800">
                    <td className="p-4 font-medium">{project.name}</td>
                    <td className="p-4 text-slate-400">
                      {project.space_name}
                    </td>
                    <td className="p-4 text-slate-400">
                      {project.owner_email}
                    </td>
                    <td className="p-4 text-slate-400">
                      {new Date(project.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold mb-4">
            Recent Activity
          </h2>

          <div className="overflow-x-auto rounded-2xl border border-slate-800">
            <table className="w-full text-left">
              <thead className="bg-slate-900 text-slate-400 text-sm">
                <tr>
                  <th className="p-4">Event</th>
                  <th className="p-4">Project</th>
                  <th className="p-4">User</th>
                  <th className="p-4">Time</th>
                </tr>
              </thead>

              <tbody>
                {activity.slice(0, 50).map((event) => (
                  <tr key={event.id} className="border-t border-slate-800">
                    <td className="p-4 font-medium">
                      {event.event_type}
                    </td>
                    <td className="p-4 text-slate-400">
                      {event.project_id}
                    </td>
                    <td className="p-4 text-slate-400">
                      {event.user_id}
                    </td>
                    <td className="p-4 text-slate-400">
                      {new Date(event.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-8 mb-12 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold">System Health</h2>

          <div className="grid md:grid-cols-3 gap-4 mt-5">
            <div>
              <div className="text-sm text-slate-400">API</div>
              <div className="text-emerald-400 font-semibold mt-1">
                ● Running
              </div>
            </div>

            <div>
              <div className="text-sm text-slate-400">Database</div>
              <div className="text-emerald-400 font-semibold mt-1">
                ● Connected
              </div>
            </div>

            <div>
              <div className="text-sm text-slate-400">AI Observability</div>
              <div className="text-emerald-400 font-semibold mt-1">
                ● Active
              </div>
            </div>
          </div>
        </section>

      </div>
    </main>
  );
}
