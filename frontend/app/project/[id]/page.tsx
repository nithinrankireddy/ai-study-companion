"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API = "http://localhost:8000";

type Project = {
  id: string;
  name: string;
  description?: string;
  space_id: string;
};

type Source = {
  material_id: string;
  chunk_index: number;
};

type QuizQuestion = {
  question: string;
  options: string[];
  answer: number;
  explanation: string;
};

type QuizResult = {
  score: number;
  total: number;
  percentage: number;
  created_at: string;
};

type AssessmentQuestion = {
  question: string;
  concept: string;
  expected_points: string[];
};

type AssessmentEvaluation = {
  score: number;
  understanding: string;
  strengths: string[];
  missing_concepts: string[];
  feedback: string;
  recommendation: string;
};

type MasteryItem = {
  concept: string;
  mastery: number;
};

type GrowthAnalysis = {
  overall_status: "improving" | "stable" | "attention";
  summary: string;
  strengths: string[];
  areas_needing_attention: string[];
  growth_insights: string[];
  next_action: string;
};

type Recommendation = {
  title: string;
  reason: string;
  action: string;
  priority: "high" | "medium" | "low";
};

export default function ProjectPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);

  // AI Tutor
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);

  // Quiz
  const [quiz, setQuiz] = useState<QuizQuestion[]>([]);
  const [quizAnswers, setQuizAnswers] = useState<number[]>([]);
  const [quizLoading, setQuizLoading] = useState(false);
  const [quizStarted, setQuizStarted] = useState(false);
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizScore, setQuizScore] = useState(0);

  // Progress
  const [previousResults, setPreviousResults] = useState<QuizResult[]>(
    []
  );

  // Assessment
  const [assessment, setAssessment] = useState<AssessmentQuestion[]>([]);
  const [assessmentAnswers, setAssessmentAnswers] = useState<string[]>([]);
  const [assessmentLoading, setAssessmentLoading] = useState(false);
  const [assessmentStarted, setAssessmentStarted] = useState(false);
  const [assessmentSubmitting, setAssessmentSubmitting] =
    useState(false);
  const [assessmentSubmitted, setAssessmentSubmitted] = useState(false);
  const [assessmentEvaluations, setAssessmentEvaluations] = useState<
    (AssessmentEvaluation | null)[]
  >([]);

  const [analytics, setAnalytics] = useState<any>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // Concept Mastery
  const [mastery, setMastery] = useState<MasteryItem[]>([]);

  // Growth Analysis
  const [growthAnalysis, setGrowthAnalysis] =
    useState<GrowthAnalysis | null>(null);

  // Recommendations
  const [recommendations, setRecommendations] =
    useState<Recommendation[]>([]);

  const [growthLoading, setGrowthLoading] = useState(false);

  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState("");

  // Activity Tracking
  async function trackActivity(
    eventType: string,
    metadata: Record<string, any> = {}
  ) {
    try {
      const token = localStorage.getItem("token");

      if (!token) return;

      await fetch(`${API}/activity/event`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          project_id: projectId,
          event_type: eventType,
          metadata,
        }),
      });
    } catch (error) {
      console.log("Activity tracking failed:", error);
    }
  }

  useEffect(() => {
    loadProject();
    loadProgress();
    loadGrowthData();
    loadAnalytics();
  }, [projectId]);

  async function loadProject() {
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
        throw new Error("Unable to load project");
      }

      const data = await response.json();

      setProject(data);
    } catch {
      setError("Unable to load project.");
    } finally {
      setPageLoading(false);
    }
  }

  async function loadProgress() {
    try {
      const token = localStorage.getItem("token");

      const response = await fetch(
        `${API}/progress/${projectId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        return;
      }

      const data = await response.json();

      setPreviousResults(data.results || []);
    } catch {
      console.log("Unable to load progress");
    }
  }

  async function askTutor() {
    if (!question.trim()) return;

    setLoading(true);
    setAnswer("");
    setSources([]);
    setError("");

    try {
      const token = localStorage.getItem("token");

      const response = await fetch(`${API}/tutor/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          project_id: projectId,
          question: question.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "AI Tutor failed");
      }

      setAnswer(data.answer || "No answer received.");
      setSources(data.sources || []);

      await trackActivity("TUTOR_ASKED", {
        question: question.trim(),
        source_count: (data.sources || []).length,
      });
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function generateQuiz() {
    setQuizLoading(true);
    setQuiz([]);
    setQuizAnswers([]);
    setQuizSubmitted(false);
    setQuizStarted(false);
    setQuizScore(0);
    setError("");

    try {
      const token = localStorage.getItem("token");

      const response = await fetch(`${API}/quiz/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          project_id: projectId,
          num_questions: 5,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Quiz generation failed"
        );
      }

      setQuiz(data.questions || []);

      setQuizAnswers(
        new Array((data.questions || []).length).fill(-1)
      );

      setQuizStarted(true);

      await trackActivity("QUIZ_GENERATED", {
        question_count: (data.questions || []).length,
      });
    } catch (err: any) {
      setError(
        err.message || "Quiz generation failed."
      );
    } finally {
      setQuizLoading(false);
    }
  }

  function selectAnswer(
    questionIndex: number,
    optionIndex: number
  ) {
    if (quizSubmitted) return;

    const updated = [...quizAnswers];

    updated[questionIndex] = optionIndex;

    setQuizAnswers(updated);
  }

  async function submitQuiz() {
    let score = 0;

    quiz.forEach((q, index) => {
      if (quizAnswers[index] === q.answer) {
        score++;
      }
    });

    setQuizScore(score);
    setQuizSubmitted(true);

    await trackActivity("QUIZ_COMPLETED", {
      score,
      total: quiz.length,
      percentage:
        quiz.length > 0
          ? (score / quiz.length) * 100
          : 0,
    });

    try {
      const token = localStorage.getItem("token");

      const response = await fetch(
        `${API}/progress/quiz`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            project_id: projectId,
            score,
            total: quiz.length,
          }),
        }
      );

      if (!response.ok) {
        console.log("Quiz result could not be saved");
        return;
      }

      await loadProgress();
      await loadGrowthData();

      // Trigger the background learning workflow.
      // This does not call Gemini from the browser; the backend processes
      // learning evidence asynchronously.
      try {
        const workflowResponse = await fetch(
          `${API}/workflow/process`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              project_id: projectId,
              trigger: "quiz_completed",
            }),
          }
        );

        if (workflowResponse.ok) {
          const workflowData = await workflowResponse.json();
          console.log(
            "Learning workflow queued:",
            workflowData
          );
        } else {
          console.log(
            "Learning workflow could not be queued"
          );
        }
      } catch (workflowError) {
        console.log(
          "Learning workflow request failed:",
          workflowError
        );
      }
    } catch (error) {
      console.log(
        "Unable to save quiz result",
        error
      );
    }
  }

  function resetQuiz() {
    setQuiz([]);
    setQuizAnswers([]);
    setQuizStarted(false);
    setQuizSubmitted(false);
    setQuizScore(0);
  }

  async function generateAssessment() {
    try {
      setAssessmentLoading(true);
      setAssessment([]);
      setAssessmentAnswers([]);
      setAssessmentEvaluations([]);
      setAssessmentSubmitted(false);
      setError("");

      const token = localStorage.getItem("token");

      const response = await fetch(
        `${API}/assessment/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            project_id: projectId,
            num_questions: 3,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Assessment generation failed"
        );
      }

      setAssessment(data.questions || []);

      setAssessmentAnswers(
        new Array(
          (data.questions || []).length
        ).fill("")
      );

      setAssessmentEvaluations(
        new Array(
          (data.questions || []).length
        ).fill(null)
      );

      setAssessmentStarted(true);

      await trackActivity("ASSESSMENT_STARTED", {
        question_count: (data.questions || []).length,
      });
    } catch (err: any) {
      console.error(
        "Assessment generation error:",
        err
      );

      setError(
        err.message ||
          "Assessment generation failed."
      );
    } finally {
      setAssessmentLoading(false);
    }
  }

  async function submitAssessment() {
    try {
      setError("");
      setAssessmentSubmitting(true);
  
      const token = localStorage.getItem("token");
  
      if (!token) {
        throw new Error(
          "You are not authenticated. Please log in again."
        );
      }
  
      if (assessment.length === 0) {
        throw new Error(
          "No assessment questions available."
        );
      }
  
      const answers = assessment.map((question, index) => ({
        question_index: index,
        question: question.question,
        answer: assessmentAnswers[index]?.trim() || "",
        concept: question.concept,
      }));
  
      console.log(
        "Submitting entire assessment in ONE Gemini request..."
      );
  
      const response = await fetch(
        `${API}/assessment/evaluate-batch`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            project_id: projectId,
            answers,
          }),
        }
      );
  
      let data;
  
      try {
        data = await response.json();
      } catch {
        throw new Error(
          "Invalid response from assessment server."
        );
      }
  
      console.log(
        "Batch assessment response:",
        data
      );
  
      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            "Assessment evaluation failed."
        );
      }
  
      if (!data.evaluations) {
        throw new Error(
          "No assessment evaluations returned."
        );
      }
  
      setAssessmentEvaluations(
        data.evaluations
      );
  
      setAssessmentSubmitted(true);
  
      // Refresh mastery
      const masteryResponse = await fetch(
        `${API}/assessment/${projectId}/mastery`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
  
      if (masteryResponse.ok) {
        const masteryData =
          await masteryResponse.json();
  
        setMastery(
          masteryData.concepts || []
        );
      }
  
      // Refresh growth + recommendations
      await loadGrowthData();
  
      await trackActivity(
        "ASSESSMENT_COMPLETED",
        {
          question_count: assessment.length,
          evaluated_count:
            data.evaluations.length,
        }
      );
  
      await trackActivity(
        "MASTERY_UPDATED",
        {
          source: "assessment",
        }
      );
  
      console.log(
        "Assessment submitted successfully."
      );
  
    } catch (err: any) {
      console.error(
        "Assessment evaluation error:",
        err
      );
  
      setError(
        err.message ||
          "Assessment evaluation failed. Please try again."
      );
  
    } finally {
      setAssessmentSubmitting(false);
    }
  }

  function resetAssessment() {
    setAssessment([]);
    setAssessmentAnswers([]);
    setAssessmentEvaluations([]);
    setAssessmentStarted(false);
    setAssessmentSubmitted(false);
    setMastery([]);
  }

  async function loadGrowthData() {
    try {
      setGrowthLoading(true);

      const token = localStorage.getItem("token");

      if (!token) {
        console.log("No authentication token found");
        return;
      }

      // Growth Analysis
      try {
        const growthResponse = await fetch(
          `${API}/growth/${projectId}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (growthResponse.ok) {
          const growthData =
            await growthResponse.json();

          if (growthData.analysis) {
            setGrowthAnalysis(
              growthData.analysis
            );
          }
        } else {
          console.log(
            "Growth API returned:",
            growthResponse.status
          );
        }
      } catch (error) {
        console.log(
          "Growth analysis request failed:",
          error
        );
      }

      // Recommendations
      try {
        const recommendationsResponse =
          await fetch(
            `${API}/growth/${projectId}/recommendations`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            }
          );

        if (recommendationsResponse.ok) {
          const recommendationData =
            await recommendationsResponse.json();

          setRecommendations(
            recommendationData.recommendations ||
              []
          );
        } else {
          console.log(
            "Recommendations API returned:",
            recommendationsResponse.status
          );
        }
      } catch (error) {
        console.log(
          "Recommendations request failed:",
          error
        );
      }
    } catch (error) {
      console.log(
        "Unable to load growth data:",
        error
      );
    } finally {
      setGrowthLoading(false);
    }
  }

  async function loadAnalytics() {
    try {
      setAnalyticsLoading(true);

      const token = localStorage.getItem("token");

      if (!token) {
        return;
      }

      const response = await fetch(
        `${API}/analytics/${projectId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        console.log(
          "Analytics API returned:",
          response.status
        );
        return;
      }

      const data = await response.json();

      console.log("Analytics:", data);

      setAnalytics(data);
    } catch (error) {
      console.log(
        "Analytics loading failed:",
        error
      );
    } finally {
      setAnalyticsLoading(false);
    }
  }

  if (pageLoading) {
    return (
      <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <p className="text-slate-400">
          Loading project...
        </p>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">
            Unable to load project
          </h1>

          <p className="text-red-400">
            {error}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900">
        <div className="max-w-6xl mx-auto px-6 py-5">

          <button
            onClick={() =>
              (window.location.href =
                `/space/${project.space_id}`)
            }
            className="text-sm text-slate-400 hover:text-white mb-3"
          >
            ← Back to Space
          </button>

          <h1 className="text-3xl font-bold">
            {project.name}
          </h1>

          {project.description && (
            <p className="text-slate-400 mt-2">
              {project.description}
            </p>
          )}

        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-900 bg-red-950/40 p-4">
            <p className="text-red-400">
              {error}
            </p>
          </div>
        )}

        {/* Study Materials */}
        <section className="mb-8">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

            <div className="flex items-center gap-3 mb-3">

              <span className="text-2xl">
                📚
              </span>

              <h2 className="text-xl font-bold">
                Study Materials
              </h2>

            </div>

            <p className="text-slate-400">
              Your uploaded study material is
              available to the AI Tutor and Quiz
              Generator.
            </p>

            <div className="mt-4 rounded-lg bg-slate-800 p-4">

              <p className="text-sm text-green-400">
                ✓ Material processed successfully
              </p>

              <p className="text-xs text-slate-500 mt-1">
                Your PDF has been extracted and
                converted into searchable chunks.
              </p>

            </div>

          </div>
        </section>

        {/* AI Tutor */}
        <section className="mb-8">

          <div className="rounded-2xl border border-blue-900/50 bg-slate-900 p-6">

            <div className="flex items-center gap-3 mb-2">

              <span className="text-3xl">
                🤖
              </span>

              <div>

                <h2 className="text-2xl font-bold">
                  AI Tutor
                </h2>

                <p className="text-sm text-slate-400">
                  Ask questions about your study
                  material
                </p>

              </div>

            </div>

            <div className="mt-6">

              <label className="block text-sm font-medium text-slate-300 mb-2">
                Your Question
              </label>

              <textarea
                value={question}
                onChange={(e) =>
                  setQuestion(e.target.value)
                }
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey
                  ) {
                    e.preventDefault();
                    askTutor();
                  }
                }}
                placeholder="Ask something about your study material..."
                className="w-full min-h-32 rounded-xl border border-slate-700 bg-slate-950 p-4 text-white placeholder-slate-500 outline-none focus:border-blue-500 resize-none"
              />

              <div className="flex justify-between items-center mt-3">

                <p className="text-xs text-slate-500">
                  Press Enter to ask • Shift +
                  Enter for new line
                </p>

                <button
                  onClick={askTutor}
                  disabled={
                    loading ||
                    !question.trim()
                  }
                  className="rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 px-6 py-3 font-semibold transition"
                >
                  {loading
                    ? "Thinking..."
                    : "Ask AI →"}
                </button>

              </div>

            </div>

            {answer && (
              <div className="mt-8">

                <h3 className="text-lg font-semibold mb-3">
                  🤖 AI Tutor Answer
                </h3>

                <div className="rounded-xl border border-slate-700 bg-slate-950 p-5">

                  <div className="whitespace-pre-wrap leading-7 text-slate-200">
                    {answer}
                  </div>

                </div>

                {sources.length > 0 && (
                  <div className="mt-5">

                    <h3 className="text-sm font-semibold text-slate-300 mb-2">
                      📖 Sources from your material
                    </h3>

                    <div className="flex flex-wrap gap-2">

                      {sources.map(
                        (source, index) => (
                          <span
                            key={index}
                            className="rounded-lg bg-slate-800 px-3 py-2 text-xs text-slate-400"
                          >
                            Material • Chunk{" "}
                            {source.chunk_index}
                          </span>
                        )
                      )}

                    </div>

                  </div>
                )}

              </div>
            )}

          </div>

        </section>

        {/* Quiz */}
        <section className="mb-8">

          <div className="rounded-2xl border border-purple-900/50 bg-slate-900 p-6">

            <div className="flex items-center gap-3 mb-2">

              <span className="text-3xl">
                📝
              </span>

              <div>

                <h2 className="text-2xl font-bold">
                  AI Quiz
                </h2>

                <p className="text-sm text-slate-400">
                  Test your knowledge from the
                  study material
                </p>

              </div>

            </div>

            {!quizStarted && (
              <div className="mt-6">

                <p className="text-slate-400 mb-5">
                  Generate 5 multiple-choice
                  questions from your uploaded
                  material.
                </p>

                <button
                  onClick={generateQuiz}
                  disabled={quizLoading}
                  className="rounded-xl bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 px-6 py-3 font-semibold transition"
                >
                  {quizLoading
                    ? "Generating Quiz..."
                    : "Generate Quiz →"}
                </button>

              </div>
            )}

            {quizStarted && (
              <div className="mt-6 space-y-6">

                {quiz.map(
                  (q, questionIndex) => (
                    <div
                      key={questionIndex}
                      className="rounded-xl border border-slate-700 bg-slate-950 p-5"
                    >

                      <h3 className="font-semibold text-lg mb-4">
                        {questionIndex + 1}.{" "}
                        {q.question}
                      </h3>

                      <div className="space-y-3">

                        {q.options.map(
                          (
                            option,
                            optionIndex
                          ) => {

                            const selected =
                              quizAnswers[
                                questionIndex
                              ] === optionIndex;

                            const correct =
                              q.answer ===
                              optionIndex;

                            let style =
                              "border-slate-700 bg-slate-900 hover:border-purple-500";

                            if (
                              !quizSubmitted &&
                              selected
                            ) {
                              style =
                                "border-purple-500 bg-purple-950/40";
                            }

                            if (
                              quizSubmitted &&
                              correct
                            ) {
                              style =
                                "border-green-600 bg-green-950/40";
                            }

                            if (
                              quizSubmitted &&
                              selected &&
                              !correct
                            ) {
                              style =
                                "border-red-600 bg-red-950/40";
                            }

                            return (
                              <button
                                key={optionIndex}
                                onClick={() =>
                                  selectAnswer(
                                    questionIndex,
                                    optionIndex
                                  )
                                }
                                className={`w-full text-left rounded-lg border p-4 transition ${style}`}
                              >

                                <span className="font-semibold mr-2">
                                  {String.fromCharCode(
                                    65 +
                                      optionIndex
                                  )}
                                  .
                                </span>

                                {option}

                              </button>
                            );
                          }
                        )}

                      </div>

                      {quizSubmitted && (
                        <div className="mt-4 rounded-lg bg-slate-900 p-4">

                          <p className="text-sm text-slate-300">

                            <span className="font-semibold">
                              Explanation:
                            </span>{" "}

                            {q.explanation}

                          </p>

                        </div>
                      )}

                    </div>
                  )
                )}

                {!quizSubmitted ? (

                  <button
                    onClick={submitQuiz}
                    disabled={quizAnswers.some(
                      (answer) =>
                        answer === -1
                    )}
                    className="w-full rounded-xl bg-green-600 hover:bg-green-700 disabled:bg-slate-700 disabled:text-slate-500 px-6 py-4 font-bold transition"
                  >
                    Submit Quiz
                  </button>

                ) : (

                  <div className="rounded-2xl border border-green-800 bg-green-950/30 p-6 text-center">

                    <p className="text-sm text-slate-400">
                      Your Score
                    </p>

                    <p className="text-5xl font-bold text-green-400 mt-2">
                      {quizScore}/
                      {quiz.length}
                    </p>

                    <p className="text-slate-300 mt-3">
                      {quizScore ===
                      quiz.length
                        ? "Excellent! 🎉"
                        : "Keep practicing! 💪"}
                    </p>

                    <button
                      onClick={resetQuiz}
                      className="mt-5 rounded-xl bg-purple-600 hover:bg-purple-700 px-6 py-3 font-semibold"
                    >
                      Generate New Quiz
                    </button>

                  </div>

                )}

              </div>
            )}

          </div>

        </section>

        {/* Open-Ended Assessment */}
        <section className="mb-8">

          <div className="rounded-2xl border border-emerald-900/50 bg-slate-900 p-6">

            <div className="flex items-center justify-between gap-4 mb-2">

              <div className="flex items-center gap-3">

                <span className="text-3xl">
                  🧠
                </span>

                <div>

                  <h2 className="text-2xl font-bold">
                    Open-Ended Assessment
                  </h2>

                  <p className="text-sm text-slate-400">
                    Explain concepts in your own
                    words and receive AI-powered
                    feedback.
                  </p>

                </div>

              </div>

              {!assessmentStarted && (
                <button
                  onClick={generateAssessment}
                  disabled={assessmentLoading}
                  className="rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:text-slate-500 px-6 py-3 font-semibold transition"
                >
                  {assessmentLoading
                    ? "Generating..."
                    : "Start Assessment →"}
                </button>
              )}

            </div>

            {assessmentStarted &&
              assessment.length > 0 && (
                <div className="mt-6 space-y-6">

                  {assessment.map(
                    (item, index) => (
                      <div
                        key={index}
                        className="rounded-xl border border-slate-700 bg-slate-950 p-5"
                      >

                        <div className="mb-4">

                          <span className="text-sm font-semibold text-emerald-400">
                            Question {index + 1}
                          </span>

                          <h3 className="mt-1 text-lg font-semibold">
                            {item.question}
                          </h3>

                          <p className="mt-2 text-xs text-slate-500">
                            Concept:{" "}
                            {item.concept}
                          </p>

                        </div>

                        <textarea
                          value={
                            assessmentAnswers[
                              index
                            ] || ""
                          }
                          onChange={(e) => {

                            const updated = [
                              ...assessmentAnswers,
                            ];

                            updated[index] =
                              e.target.value;

                            setAssessmentAnswers(
                              updated
                            );

                          }}
                          disabled={
                            assessmentSubmitted
                          }
                          placeholder="Write your answer here..."
                          rows={5}
                          className="w-full rounded-xl border border-slate-700 bg-slate-900 p-4 text-white placeholder-slate-500 outline-none focus:border-emerald-500 resize-none disabled:opacity-60"
                        />

                        {assessmentSubmitted &&
                          assessmentEvaluations[
                            index
                          ] && (
                            <div className="mt-5 space-y-4 rounded-xl border border-emerald-900/50 bg-slate-900 p-5">

                              <div>

                                <p className="text-sm text-slate-400">
                                  Score
                                </p>

                                <p className="text-3xl font-bold text-emerald-400 mt-1">
                                  {
                                    assessmentEvaluations[
                                      index
                                    ]!.score
                                  }
                                  /100
                                </p>

                              </div>

                              <div>

                                <h4 className="font-semibold">
                                  Understanding
                                </h4>

                                <p className="mt-1 text-sm leading-6 text-slate-300">
                                  {
                                    assessmentEvaluations[
                                      index
                                    ]!.understanding
                                  }
                                </p>

                              </div>

                              {assessmentEvaluations[
                                index
                              ]!.strengths.length >
                                0 && (
                                <div>

                                  <h4 className="font-semibold">
                                    Strengths
                                  </h4>

                                  <ul className="mt-1 list-disc pl-5 text-sm leading-6 text-slate-300">

                                    {assessmentEvaluations[
                                      index
                                    ]!.strengths.map(
                                      (
                                        strength,
                                        i
                                      ) => (
                                        <li key={i}>
                                          {strength}
                                        </li>
                                      )
                                    )}

                                  </ul>

                                </div>
                              )}

                              {assessmentEvaluations[
                                index
                              ]!.missing_concepts
                                .length >
                                0 && (
                                <div>

                                  <h4 className="font-semibold">
                                    Missing Concepts
                                  </h4>

                                  <ul className="mt-1 list-disc pl-5 text-sm leading-6 text-slate-300">

                                    {assessmentEvaluations[
                                      index
                                    ]!.missing_concepts.map(
                                      (
                                        concept,
                                        i
                                      ) => (
                                        <li key={i}>
                                          {concept}
                                        </li>
                                      )
                                    )}

                                  </ul>

                                </div>
                              )}

                              <div>

                                <h4 className="font-semibold">
                                  Feedback
                                </h4>

                                <p className="mt-1 text-sm leading-6 text-slate-300">
                                  {
                                    assessmentEvaluations[
                                      index
                                    ]!.feedback
                                  }
                                </p>

                              </div>

                              <div>

                                <h4 className="font-semibold">
                                  Recommendation
                                </h4>

                                <p className="mt-1 text-sm leading-6 text-slate-300">
                                  {
                                    assessmentEvaluations[
                                      index
                                    ]!.recommendation
                                  }
                                </p>

                              </div>

                            </div>
                          )}

                      </div>
                    )
                  )}

                  {!assessmentSubmitted ? (

                    <button
                    onClick={submitAssessment}
                    disabled={
                      assessmentSubmitting ||
                      assessmentAnswers.some(
                        (answer) => !answer.trim()
                      )
                    }
                    className="w-full rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:text-slate-500 px-6 py-4 font-bold transition"
                  >
                    {assessmentSubmitting
                      ? "⏳ Evaluating Your Answers..."
                      : "Submit Assessment"}
                  </button>

                  ) : (

                    <button
                      onClick={resetAssessment}
                      className="rounded-xl bg-slate-700 hover:bg-slate-600 px-6 py-3 font-semibold transition"
                    >
                      Take New Assessment
                    </button>

                  )}

                </div>
              )}

            {assessmentSubmitted &&
              mastery.length > 0 && (
                <div className="mt-8 rounded-xl border border-slate-700 bg-slate-950 p-5">

                  <h3 className="text-xl font-bold">
                    📈 Concept Mastery
                  </h3>

                  <p className="text-sm text-slate-400 mt-1">
                    Your estimated mastery based
                    on assessment performance.
                  </p>

                  <div className="mt-5 space-y-5">

                    {mastery.map(
                      (item, index) => (
                        <div key={index}>

                          <div className="flex justify-between items-center mb-2">

                            <span className="font-medium text-slate-300">
                              {item.concept}
                            </span>

                            <span className="font-semibold text-emerald-400">
                              {Math.round(
                                item.mastery
                              )}
                              %
                            </span>

                          </div>

                          <div className="h-2 overflow-hidden rounded-full bg-slate-800">

                            <div
                              className="h-full rounded-full bg-emerald-500 transition-all"
                              style={{
                                width: `${Math.min(
                                  100,
                                  Math.max(
                                    0,
                                    item.mastery
                                  )
                                )}%`,
                              }}
                            />

                          </div>

                        </div>
                      )
                    )}

                  </div>

                </div>
              )}

          </div>

        </section>

        {/* Growth Analysis */}
        <section className="mb-8">

          <div className="rounded-2xl border border-cyan-900/50 bg-slate-900 p-6">

            <div className="flex items-center gap-3 mb-2">

              <span className="text-3xl">
                📈
              </span>

              <div>

                <h2 className="text-2xl font-bold">
                  Growth Analysis
                </h2>

                <p className="text-sm text-slate-400">
                  Understand how your learning is
                  progressing.
                </p>

              </div>

            </div>

            {growthLoading ? (

              <div className="mt-6 rounded-xl bg-slate-800 p-5">

                <p className="text-slate-400">
                  Analyzing your learning progress...
                </p>

              </div>

            ) : growthAnalysis ? (

              <div className="mt-6 space-y-5">

                <div className="rounded-xl bg-slate-800 p-5">

                  <p className="text-sm text-slate-400">
                    Overall Progress
                  </p>

                  <p className="text-2xl font-bold mt-1 capitalize">
                    {
                      growthAnalysis.overall_status
                    }
                  </p>

                  <p className="text-sm text-slate-300 mt-3">
                    {growthAnalysis.summary}
                  </p>

                </div>

                {growthAnalysis.strengths.length >
                  0 && (
                  <div className="rounded-xl bg-slate-800 p-5">

                    <h3 className="font-semibold text-green-400">
                      💪 Strengths
                    </h3>

                    <ul className="mt-3 list-disc pl-5 space-y-1 text-sm text-slate-300">

                      {growthAnalysis.strengths.map(
                        (
                          strength,
                          index
                        ) => (
                          <li key={index}>
                            {strength}
                          </li>
                        )
                      )}

                    </ul>

                  </div>
                )}

                {growthAnalysis
                  .areas_needing_attention
                  .length > 0 && (
                  <div className="rounded-xl bg-slate-800 p-5">

                    <h3 className="font-semibold text-yellow-400">
                      ⚠️ Areas Requiring Attention
                    </h3>

                    <ul className="mt-3 list-disc pl-5 space-y-1 text-sm text-slate-300">

                      {growthAnalysis.areas_needing_attention.map(
                        (
                          area,
                          index
                        ) => (
                          <li key={index}>
                            {area}
                          </li>
                        )
                      )}

                    </ul>

                  </div>
                )}

                {growthAnalysis
                  .growth_insights
                  .length > 0 && (
                  <div className="rounded-xl bg-slate-800 p-5">

                    <h3 className="font-semibold text-cyan-400">
                      🔎 Growth Insights
                    </h3>

                    <ul className="mt-3 list-disc pl-5 space-y-1 text-sm text-slate-300">

                      {growthAnalysis.growth_insights.map(
                        (
                          insight,
                          index
                        ) => (
                          <li key={index}>
                            {insight}
                          </li>
                        )
                      )}

                    </ul>

                  </div>
                )}

                <div className="rounded-xl border border-cyan-800 bg-cyan-950/30 p-5">

                  <h3 className="font-semibold text-cyan-300">
                    🎯 Recommended Next Action
                  </h3>

                  <p className="mt-2 text-slate-200">
                    {growthAnalysis.next_action}
                  </p>

                </div>

              </div>

            ) : (

              <div className="mt-6 rounded-xl bg-slate-800 p-5">

                <p className="text-slate-400">
                  Complete a quiz or assessment
                  to generate your growth analysis.
                </p>

              </div>

            )}

          </div>

        </section>

        {/* Recommendations */}
        <section className="mb-8">

          <div className="rounded-2xl border border-orange-900/50 bg-slate-900 p-6">

            <div className="flex items-center gap-3 mb-2">

              <span className="text-3xl">
                🎯
              </span>

              <div>

                <h2 className="text-2xl font-bold">
                  Recommended Next Steps
                </h2>

                <p className="text-sm text-slate-400">
                  Personalized actions based on
                  your learning evidence.
                </p>

              </div>

            </div>

            {recommendations.length === 0 ? (

              <div className="mt-6 rounded-xl bg-slate-800 p-5">

                <p className="text-slate-400">
                  Complete a quiz or assessment
                  to receive personalized
                  recommendations.
                </p>

              </div>

            ) : (

              <div className="mt-6 space-y-4">

                {recommendations.map(
                  (
                    recommendation,
                    index
                  ) => (

                    <div
                      key={index}
                      className="rounded-xl border border-slate-700 bg-slate-950 p-5"
                    >

                      <div className="flex justify-between items-start gap-4">

                        <div>

                          <h3 className="font-semibold text-lg">
                            {
                              recommendation.title
                            }
                          </h3>

                          <p className="text-sm text-slate-400 mt-2">
                            {
                              recommendation.reason
                            }
                          </p>

                        </div>

                        <span
                          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                            recommendation.priority ===
                            "high"
                              ? "bg-red-950 text-red-400"
                              : recommendation.priority ===
                                "medium"
                              ? "bg-yellow-950 text-yellow-400"
                              : "bg-green-950 text-green-400"
                          }`}
                        >
                          {
                            recommendation.priority
                          }
                        </span>

                      </div>

                      <div className="mt-4 rounded-lg bg-slate-900 p-4">

                        <p className="text-xs text-slate-500 uppercase tracking-wide">
                          Action
                        </p>

                        <p className="text-sm text-slate-200 mt-1">
                          {
                            recommendation.action
                          }
                        </p>

                      </div>

                    </div>

                  )
                )}

              </div>

            )}

          </div>

        </section>

        {/* Learning Progress */}
        <section>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

            <div className="flex items-center gap-3">

              <span className="text-2xl">
                📊
              </span>

              <div>

                <h2 className="text-xl font-bold">
                  Learning Progress
                </h2>

                <p className="text-sm text-slate-400 mt-1">
                  Track your quiz performance.
                </p>

              </div>

            </div>

            {previousResults.length === 0 ? (

              <div className="mt-5 rounded-xl bg-slate-800 p-5">

                <p className="text-slate-400">
                  Complete a quiz to start
                  tracking your progress.
                </p>

              </div>

            ) : (

              <>

                <div className="grid md:grid-cols-3 gap-4 mt-5">

                  <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                      Quizzes Completed
                    </p>

                    <p className="text-2xl font-bold mt-1">
                      {
                        previousResults.length
                      }
                    </p>

                  </div>

                  <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                      Latest Score
                    </p>

                    <p className="text-2xl font-bold mt-1">

                      {
                        previousResults[0]
                          .score
                      }
                      /
                      {
                        previousResults[0]
                          .total
                      }

                    </p>

                  </div>

                  <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                      Latest Percentage
                    </p>

                    <p className="text-2xl font-bold mt-1">

                      {Math.round(
                        previousResults[0]
                          .percentage
                      )}
                      %

                    </p>

                  </div>

                </div>

                <div className="mt-6">

                  <h3 className="font-semibold mb-3">
                    Quiz History
                  </h3>

                  <div className="space-y-2">

                    {previousResults.map(
                      (
                        result,
                        index
                      ) => (

                        <div
                          key={index}
                          className="flex flex-col md:flex-row md:justify-between md:items-center gap-2 rounded-lg bg-slate-800 px-4 py-3"
                        >

                          <span className="text-slate-300">

                            Quiz{" "}
                            {
                              previousResults.length -
                                index
                            }

                          </span>

                          <span className="font-semibold">

                            {result.score}/
                            {result.total}

                          </span>

                          <span className="text-blue-400">

                            {Math.round(
                              result.percentage
                            )}
                            %

                          </span>

                        </div>

                      )
                    )}

                  </div>

                </div>

              </>

            )}

          </div>

        </section>

        {/* Analytics Dashboard */}
        <section className="mt-8 mb-8">
          <div className="rounded-2xl border border-indigo-900/50 bg-slate-900 p-6">

            <div className="flex items-center gap-3 mb-2">
              <span className="text-3xl">
                📊
              </span>

              <div>
                <h2 className="text-2xl font-bold">
                  Learning Analytics
                </h2>

                <p className="text-sm text-slate-400">
                  Overview of your learning activity,
                  performance and AI usage.
                </p>
              </div>
            </div>

            {analyticsLoading ? (
              <div className="mt-6 rounded-xl bg-slate-800 p-5">
                <p className="text-slate-400">
                  Loading analytics...
                </p>
              </div>
            ) : !analytics ? (
              <div className="mt-6 rounded-xl bg-slate-800 p-5">
                <p className="text-slate-400">
                  No analytics available yet.
                </p>
              </div>
            ) : (
              <div className="mt-6 space-y-6">

                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

                  <div className="rounded-xl bg-slate-800 p-5">
                    <p className="text-sm text-slate-400">
                      Quiz Attempts
                    </p>

                    <p className="text-3xl font-bold mt-2">
                      {analytics.quiz?.attempts ?? 0}
                    </p>
                  </div>

                  <div className="rounded-xl bg-slate-800 p-5">
                    <p className="text-sm text-slate-400">
                      Average Quiz Score
                    </p>

                    <p className="text-3xl font-bold text-emerald-400 mt-2">
                      {analytics.quiz?.average_percentage != null
                        ? `${Number(
                            analytics.quiz.average_percentage
                          ).toFixed(1)}%`
                        : "0%"}
                    </p>
                  </div>

                  <div className="rounded-xl bg-slate-800 p-5">
                    <p className="text-sm text-slate-400">
                      Assessment Attempts
                    </p>

                    <p className="text-3xl font-bold mt-2">
                      {analytics.assessment?.attempts ?? 0}
                    </p>
                  </div>

                  <div className="rounded-xl bg-slate-800 p-5">
                    <p className="text-sm text-slate-400">
                      Tutor Questions
                    </p>

                    <p className="text-3xl font-bold text-purple-400 mt-2">
                      {analytics.ai_activity?.tutor_questions ?? 0}
                    </p>
                  </div>

                </div>

                {/* Quiz + Assessment */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                  <div className="rounded-xl bg-slate-800 p-5">
                    <h3 className="text-lg font-semibold">
                      📝 Quiz Performance
                    </h3>

                    <div className="mt-5 space-y-4">

                      <div className="flex justify-between">
                        <span className="text-slate-400">
                          Attempts
                        </span>

                        <span className="font-semibold">
                          {analytics.quiz?.attempts ?? 0}
                        </span>
                      </div>

                      <div className="flex justify-between">
                        <span className="text-slate-400">
                          Average Score
                        </span>

                        <span className="font-semibold text-emerald-400">
                          {analytics.quiz?.average_percentage != null
                            ? `${Number(
                                analytics.quiz.average_percentage
                              ).toFixed(1)}%`
                            : "0%"}
                        </span>
                      </div>

                      <div className="flex justify-between">
                        <span className="text-slate-400">
                          Best Score
                        </span>

                        <span className="font-semibold text-yellow-400">
                          {analytics.quiz?.best_percentage != null
                            ? `${Number(
                                analytics.quiz.best_percentage
                              ).toFixed(1)}%`
                            : "0%"}
                        </span>
                      </div>

                    </div>
                  </div>

                  <div className="rounded-xl bg-slate-800 p-5">
                    <h3 className="text-lg font-semibold">
                      🎯 Assessment Performance
                    </h3>

                    <div className="mt-5 space-y-4">

                      <div className="flex justify-between">
                        <span className="text-slate-400">
                          Attempts
                        </span>

                        <span className="font-semibold">
                          {analytics.assessment?.attempts ?? 0}
                        </span>
                      </div>

                      <div className="flex justify-between">
                        <span className="text-slate-400">
                          Average Score
                        </span>

                        <span className="font-semibold text-blue-400">
                          {analytics.assessment?.average_score != null
                            ? `${Number(
                                analytics.assessment.average_score
                              ).toFixed(1)}%`
                            : "0%"}
                        </span>
                      </div>

                    </div>
                  </div>

                </div>

                {/* AI Activity */}
                <div className="rounded-xl bg-slate-800 p-5">

                  <h3 className="text-lg font-semibold">
                    🤖 AI Learning Activity
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">

                    <div className="rounded-lg bg-slate-900 p-4">
                      <p className="text-sm text-slate-400">
                        Tutor Questions
                      </p>

                      <p className="text-2xl font-bold text-purple-400 mt-2">
                        {analytics.ai_activity?.tutor_questions ?? 0}
                      </p>
                    </div>

                    <div className="rounded-lg bg-slate-900 p-4">
                      <p className="text-sm text-slate-400">
                        Quizzes Generated
                      </p>

                      <p className="text-2xl font-bold text-cyan-400 mt-2">
                        {analytics.ai_activity?.quizzes_generated ?? 0}
                      </p>
                    </div>

                  </div>
                </div>

                {/* Concept Mastery */}
                <div className="rounded-xl bg-slate-800 p-5">

                  <h3 className="text-lg font-semibold">
                    🧠 Concept Mastery
                  </h3>

                  {analytics.mastery?.length > 0 ? (
                    <div className="mt-5 space-y-4">

                      {analytics.mastery.map(
                        (item: any, index: number) => {
                          const masteryValue = Math.min(
                            100,
                            Math.max(
                              0,
                              Number(
                                item.mastery ??
                                item.score ??
                                0
                              )
                            )
                          );

                          return (
                            <div key={index}>

                              <div className="flex justify-between items-center mb-2">
                                <span className="text-sm text-slate-300">
                                  {item.concept}
                                </span>

                                <span className="text-sm font-semibold text-emerald-400">
                                  {Math.round(
                                    masteryValue
                                  )}
                                  %
                                </span>
                              </div>

                              <div className="h-2 overflow-hidden rounded-full bg-slate-900">
                                <div
                                  className="h-full rounded-full bg-emerald-500 transition-all"
                                  style={{
                                    width: `${masteryValue}%`,
                                  }}
                                />
                              </div>

                            </div>
                          );
                        }
                      )}

                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-slate-500">
                      Complete an assessment to build
                      concept mastery.
                    </p>
                  )}

                </div>

                {/* Activity */}
                <div className="rounded-xl bg-slate-800 p-5">

                  <h3 className="text-lg font-semibold">
                    📈 Activity Summary
                  </h3>

                  {analytics.activity?.length > 0 ? (
                    <div className="mt-5 overflow-x-auto">

                      <table className="w-full text-left text-sm">

                        <thead>
                          <tr className="border-b border-slate-700 text-slate-400">
                            <th className="px-3 py-3">
                              Activity
                            </th>

                            <th className="px-3 py-3">
                              Count
                            </th>
                          </tr>
                        </thead>

                        <tbody>
                          {analytics.activity.map(
                            (item: any, index: number) => (
                              <tr
                                key={index}
                                className="border-b border-slate-900"
                              >
                                <td className="px-3 py-3 text-slate-300">
                                  {item.event_type}
                                </td>

                                <td className="px-3 py-3 font-semibold">
                                  {item.count}
                                </td>
                              </tr>
                            )
                          )}
                        </tbody>

                      </table>

                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-slate-500">
                      No activity recorded yet.
                    </p>
                  )}

                </div>

              </div>
            )}

          </div>
        </section>

      </div>

    </main>
  );
}