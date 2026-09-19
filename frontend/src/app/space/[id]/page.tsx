"use client";

import { useEffect, useRef, useState } from "react";

const API = "http://localhost:8000";

export default function SpacePage() {
  const [space, setSpace] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);

  // Create project states
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [goal, setGoal] = useState("");

  // Upload states
  const [selectedFiles, setSelectedFiles] = useState<{
    [projectId: string]: File | null;
  }>({});

  const [uploadStatus, setUploadStatus] = useState<{
    [projectId: string]: string;
  }>({});

  const [materialIds, setMaterialIds] = useState<{
    [projectId: string]: string;
  }>({});

  const [uploading, setUploading] = useState<{
    [projectId: string]: boolean;
  }>({});

  const fileInputRefs = useRef<{
    [projectId: string]: HTMLInputElement | null;
  }>({});

  // ==============================
  // LOAD SELECTED SPACE
  // ==============================

  useEffect(() => {
    const saved = localStorage.getItem("selectedSpace");

    if (saved) {
      const selectedSpace = JSON.parse(saved);

      setSpace(selectedSpace);
      loadProjects(selectedSpace.id);
    }
  }, []);

  // ==============================
  // LOAD PROJECTS
  // ==============================

  const loadProjects = async (spaceId: string) => {
    try {
      const token = localStorage.getItem("token");

      const response = await fetch(
        `${API}/workspace/spaces/${spaceId}/projects`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setProjects(data);
      } else {
        console.error("Failed to load projects");
      }
    } catch (error) {
      console.error("Error loading projects:", error);
    }
  };

  // ==============================
  // CREATE PROJECT
  // ==============================

  const createProject = async () => {
    if (!name.trim() || !space) return;

    try {
      const token = localStorage.getItem("token");

      const response = await fetch(
        `${API}/workspace/spaces/${space.id}/projects`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            name,
            description,
            learning_goal: goal,
          }),
        }
      );

      if (response.ok) {
        const project = await response.json();

        setProjects((prev) => [...prev, project]);

        setName("");
        setDescription("");
        setGoal("");
      } else {
        const error = await response.json();
        alert(error.detail || "Failed to create project");
      }
    } catch (error) {
      console.error("Create project error:", error);
      alert("Unable to create project");
    }
  };

  // ==============================
  // OPEN PROJECT
  // ==============================

  const openProject = (projectId: string) => {
    console.log("Opening project:", projectId);

    window.location.href = `/project/${projectId}`;
  };

  // ==============================
  // SELECT PDF
  // ==============================

  const handleFileSelect = (
    projectId: string,
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (file.type !== "application/pdf") {
      setUploadStatus((prev) => ({
        ...prev,
        [projectId]: "❌ Only PDF files are supported",
      }));

      return;
    }

    setSelectedFiles((prev) => ({
      ...prev,
      [projectId]: file,
    }));

    setUploadStatus((prev) => ({
      ...prev,
      [projectId]: `Selected: ${file.name}`,
    }));
  };

  // ==============================
  // CHECK MATERIAL STATUS
  // ==============================

  const pollMaterialStatus = async (
    projectId: string,
    materialId: string
  ) => {
    const token = localStorage.getItem("token");

    try {
      const response = await fetch(
        `${API}/materials/${materialId}/status`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        setUploadStatus((prev) => ({
          ...prev,
          [projectId]: "❌ Could not check processing status",
        }));

        setUploading((prev) => ({
          ...prev,
          [projectId]: false,
        }));

        return;
      }

      const data = await response.json();

      console.log("Material status:", data);

      // READY
      if (data.status === "ready") {
        setUploadStatus((prev) => ({
          ...prev,
          [projectId]: "✅ PDF processed successfully",
        }));

        setUploading((prev) => ({
          ...prev,
          [projectId]: false,
        }));

        return;
      }

      // FAILED
      if (data.status === "failed") {
        setUploadStatus((prev) => ({
          ...prev,
          [projectId]: "❌ PDF processing failed",
        }));

        setUploading((prev) => ({
          ...prev,
          [projectId]: false,
        }));

        return;
      }

      // QUEUED / PROCESSING
      setUploadStatus((prev) => ({
        ...prev,
        [projectId]: `⏳ Processing... (${data.status})`,
      }));

      // Check again after 2 seconds
      setTimeout(() => {
        pollMaterialStatus(projectId, materialId);
      }, 2000);
    } catch (error) {
      console.error("Status check error:", error);

      setUploadStatus((prev) => ({
        ...prev,
        [projectId]: "❌ Error checking status",
      }));

      setUploading((prev) => ({
        ...prev,
        [projectId]: false,
      }));
    }
  };

  // ==============================
  // UPLOAD PDF
  // ==============================

  const handleUpload = async (projectId: string) => {
    const file = selectedFiles[projectId];

    if (!file) {
      setUploadStatus((prev) => ({
        ...prev,
        [projectId]: "⚠️ Please select a PDF first",
      }));

      return;
    }

    try {
      setUploading((prev) => ({
        ...prev,
        [projectId]: true,
      }));

      setUploadStatus((prev) => ({
        ...prev,
        [projectId]: "⬆️ Uploading PDF...",
      }));

      const token = localStorage.getItem("token");

      if (!token) {
        setUploadStatus((prev) => ({
          ...prev,
          [projectId]: "❌ Authentication token not found",
        }));

        setUploading((prev) => ({
          ...prev,
          [projectId]: false,
        }));

        return;
      }

      const formData = new FormData();

      formData.append("file", file);

      const response = await fetch(
        `${API}/materials/upload/${projectId}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      const data = await response.json();

      console.log("Upload response:", data);

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      const materialId = data.material_id;

      setMaterialIds((prev) => ({
        ...prev,
        [projectId]: materialId,
      }));

      setUploadStatus((prev) => ({
        ...prev,
        [projectId]: "⏳ PDF uploaded. Processing...",
      }));

      // Start checking status
      pollMaterialStatus(projectId, materialId);
    } catch (error: any) {
      console.error("Upload error:", error);

      setUploadStatus((prev) => ({
        ...prev,
        [projectId]: `❌ ${error.message || "Upload failed"}`,
      }));

      setUploading((prev) => ({
        ...prev,
        [projectId]: false,
      }));
    }
  };

  // ==============================
  // LOADING
  // ==============================

  if (!space) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <p className="text-slate-400">Loading space...</p>
      </div>
    );
  }

  // ==============================
  // UI
  // ==============================

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* HEADER */}
      <header className="border-b border-slate-800 p-6">

        <button
          type="button"
          onClick={() => {
            window.location.href = "/";
          }}
          className="text-blue-400 hover:text-blue-300 cursor-pointer"
        >
          ← Back to Spaces
        </button>

        <h1 className="text-3xl font-bold mt-4">
          {space.name}
        </h1>

        <p className="text-slate-400 mt-2">
          {space.description}
        </p>

      </header>

      {/* CONTENT */}
      <section className="max-w-6xl mx-auto p-8">

        {/* CREATE PROJECT */}
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6">

          <h2 className="text-xl font-bold">
            Create Project
          </h2>

          <div className="space-y-3 mt-5">

            <input
              placeholder="Project name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg bg-slate-800 border border-slate-700 p-3 outline-none focus:border-blue-500"
            />

            <input
              placeholder="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg bg-slate-800 border border-slate-700 p-3 outline-none focus:border-blue-500"
            />

            <input
              placeholder="Learning goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="w-full rounded-lg bg-slate-800 border border-slate-700 p-3 outline-none focus:border-blue-500"
            />

            <button
              type="button"
              onClick={createProject}
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 py-3 font-semibold transition cursor-pointer"
            >
              + Create Project
            </button>

          </div>

        </div>

        {/* PROJECTS */}
        <h2 className="text-2xl font-bold mt-10">
          Projects
        </h2>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mt-5">

          {projects.length === 0 && (
            <p className="text-slate-500">
              No projects yet. Create your first project.
            </p>
          )}

          {projects.map((project) => (

            <div
              key={project.id}
              className="rounded-2xl bg-slate-900 border border-slate-800 p-6"
            >

              {/* PROJECT INFO */}

              <h3 className="text-xl font-bold">
                {project.name}
              </h3>

              <p className="text-slate-400 mt-2">
                {project.description || "No description"}
              </p>

              <p className="text-sm text-blue-400 mt-3">
                Goal: {project.learning_goal || "No learning goal"}
              </p>

              {/* OPEN PROJECT */}

              <button
                type="button"
                onClick={() => {
                  console.log("PROJECT CLICKED:", project.id);
                  window.location.assign(`/project/${project.id}`);
                }}
                style={{
                  display: "block",
                  width: "100%",
                  marginTop: "20px",
                  padding: "12px 16px",
                  backgroundColor: "#2563eb",
                  color: "white",
                  border: "none",
                  borderRadius: "8px",
                  fontSize: "16px",
                  fontWeight: "600",
                  cursor: "pointer",
                  textAlign: "center",
                }}
              >
                Open Project →
              </button>

              {/* DIVIDER */}

              <div className="border-t border-slate-800 my-5" />

              {/* MATERIAL UPLOAD */}

              <h4 className="font-semibold text-lg">
                📄 Study Material
              </h4>

              <p className="text-xs text-slate-500 mt-1">
                Upload a PDF for this project
              </p>

              {/* FILE INPUT */}

              <input
                ref={(element) => {
                  fileInputRefs.current[project.id] = element;
                }}
                type="file"
                accept=".pdf,application/pdf"
                onChange={(e) =>
                  handleFileSelect(project.id, e)
                }
                className="hidden"
              />

              <button
                type="button"
                onClick={() =>
                  fileInputRefs.current[project.id]?.click()
                }
                disabled={uploading[project.id]}
                className="w-full mt-4 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 py-3 text-sm transition disabled:opacity-50 cursor-pointer"
              >
                📁 Choose PDF
              </button>

              {/* SELECTED FILE */}

              {selectedFiles[project.id] && (
                <div className="mt-3 rounded-lg bg-slate-800 p-3">

                  <p className="text-sm text-white truncate">
                    📄 {selectedFiles[project.id]?.name}
                  </p>

                  <p className="text-xs text-slate-500 mt-1">
                    {(
                      (selectedFiles[project.id]?.size || 0) /
                      1024 /
                      1024
                    ).toFixed(2)}{" "}
                    MB
                  </p>

                </div>
              )}

              {/* UPLOAD BUTTON */}

              <button
                type="button"
                onClick={() => handleUpload(project.id)}
                disabled={
                  !selectedFiles[project.id] ||
                  uploading[project.id]
                }
                className="w-full mt-3 rounded-lg bg-green-600 hover:bg-green-700 py-3 font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading[project.id]
                  ? "Processing..."
                  : "⬆️ Upload PDF"}
              </button>

              {/* STATUS */}

              {uploadStatus[project.id] && (
                <div className="mt-4 rounded-lg bg-slate-800 p-3">

                  <p className="text-sm">
                    {uploadStatus[project.id]}
                  </p>

                </div>
              )}

              {/* MATERIAL ID */}

              {materialIds[project.id] && (
                <div className="mt-3">

                  <p className="text-xs text-slate-500">
                    Material ID
                  </p>

                  <p className="text-xs text-slate-400 break-all mt-1">
                    {materialIds[project.id]}
                  </p>

                </div>
              )}

            </div>

          ))}

        </div>

      </section>

    </main>
  );
}