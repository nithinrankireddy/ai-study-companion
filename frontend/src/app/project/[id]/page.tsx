"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

const API = "http://localhost:8000";

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();

  const projectId = params.id as string;

  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!projectId) return;

    const loadProject = async () => {
      try {
        const token = localStorage.getItem("token");

        const response = await fetch(
          `${API}/workspace/projects/${projectId}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error("Project could not be loaded");
        }

        const data = await response.json();
        setProject(data);
      } catch (err) {
        console.error(err);
        setError("Unable to load project.");
      } finally {
        setLoading(false);
      }
    };

    loadProject();
  }, [projectId]);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <p className="text-slate-400">Loading project...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-slate-950 text-white p-8">
        <button
          onClick={() => router.back()}
          className="text-blue-400 mb-8"
        >
          ← Back
        </button>

        <div className="max-w-3xl mx-auto rounded-2xl bg-slate-900 border border-slate-800 p-8">
          <h1 className="text-2xl font-bold">
            Project
          </h1>

          <p className="text-red-400 mt-4">
            {error}
          </p>

          <p className="text-slate-500 mt-2 text-sm">
            Project ID: {projectId}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* HEADER */}
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto p-6">

          <button
            onClick={() => router.back()}
            className="text-blue-400 hover:text-blue-300"
          >
            ← Back to Projects
          </button>

          <h1 className="text-4xl font-bold mt-6">
            {project?.name || "Project"}
          </h1>

          <p className="text-slate-400 mt-3">
            {project?.description || "No description available"}
          </p>

        </div>
      </header>

      {/* PROJECT CONTENT */}
      <section className="max-w-6xl mx-auto p-8">

        <div className="grid md:grid-cols-3 gap-6">

          {/* MAIN */}
          <div className="md:col-span-2">

            <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6">

              <h2 className="text-2xl font-bold">
                Learning Goal
              </h2>

              <p className="text-blue-400 mt-3">
                {project?.learning_goal || "No learning goal specified"}
              </p>

            </div>

            <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 mt-6">

              <h2 className="text-2xl font-bold">
                Study Materials
              </h2>

              <p className="text-slate-400 mt-2">
                Your uploaded study materials will appear here.
              </p>

              <div className="mt-6 rounded-xl border border-dashed border-slate-700 p-8 text-center">

                <p className="text-4xl">
                  📄
                </p>

                <p className="font-semibold mt-3">
                  No materials yet
                </p>

                <p className="text-slate-500 text-sm mt-1">
                  Upload a PDF to start studying.
                </p>

              </div>

            </div>

          </div>

          {/* SIDEBAR */}
          <div>

            <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6">

              <h2 className="text-xl font-bold">
                Project Information
              </h2>

              <div className="mt-5 space-y-4">

                <div>
                  <p className="text-sm text-slate-500">
                    Project Name
                  </p>

                  <p className="mt-1 font-semibold">
                    {project?.name || "Unknown"}
                  </p>
                </div>

                <div>
                  <p className="text-sm text-slate-500">
                    Learning Goal
                  </p>

                  <p className="mt-1 text-blue-400">
                    {project?.learning_goal || "Not specified"}
                  </p>
                </div>

                <div>
                  <p className="text-sm text-slate-500">
                    Project ID
                  </p>

                  <p className="mt-1 text-xs text-slate-400 break-all">
                    {projectId}
                  </p>
                </div>

              </div>

            </div>

          </div>

        </div>

      </section>

    </main>
  );
}