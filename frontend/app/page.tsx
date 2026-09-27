import Link from "next/link";
import { ArrowRight, MessageSquare, BarChart2, Database, Bot, Layers, Brain, Check } from "lucide-react";
import type { Persona } from "@/types";
import { getPersonas } from "@/lib/backend";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Evidence-based AI discussions",
  description:
    "Watch AI agents with distinct personas debate transformer architecture choices in real time. Grounded on a real knowledge base. Analyzed for opinion dynamics.",
};

// Deterministic color for a persona by simple index (server-safe, no hash needed here).
const STANCE_COLORS = [
  { text: "text-blue-700 dark:text-blue-300", bg: "bg-blue-100 dark:bg-blue-900" },
  { text: "text-red-700 dark:text-red-300", bg: "bg-red-100 dark:bg-red-900" },
  { text: "text-teal-700 dark:text-teal-300", bg: "bg-teal-100 dark:bg-teal-900" },
  { text: "text-amber-700 dark:text-amber-300", bg: "bg-amber-100 dark:bg-amber-900" },
];

export default async function HomePage() {
  let personas: Persona[] = [];
  let personasUnavailable = false;
  try {
    personas = await getPersonas();
  } catch {
    // Keep the introduction available while the backend is offline.
    personasUnavailable = true;
  }

  const steps = [
    {
      icon: MessageSquare,
      title: "Choose a topic and agents",
      body: "Write a discussion brief, select participating AI personas, and configure how many rounds to run.",
    },
    {
      icon: Layers,
      title: "Watch them debate over multiple rounds",
      body: "Agents exchange messages through a directed graph. Each agent only reads from its assigned predecessors.",
    },
    {
      icon: Database,
      title: "Evidence from a real knowledge base",
      body: "Agents retrieve relevant evidence from your configured research collection using hybrid search.",
    },
    {
      icon: BarChart2,
      title: "Analyze opinion trajectories",
      body: "Explore changes in stance, agreement, influence, and sentiment across the discussion.",
    },
  ];

  const pipeline = [
    { label: "Knowledge", sub: "Week 1", icon: Database, color: "from-violet-500 to-violet-700" },
    { label: "Agents", sub: "Week 2", icon: Bot, color: "from-blue-500 to-blue-700" },
    { label: "Discussion", sub: "Week 3", icon: MessageSquare, color: "from-indigo-500 to-indigo-700" },
    { label: "Analytics", sub: "Week 4", icon: BarChart2, color: "from-teal-500 to-teal-700" },
    { label: "Frontend", sub: "Week 5", icon: Brain, color: "from-emerald-500 to-emerald-700" },
  ];

  return (
    <div className="flex flex-col">
      {/* ====== Hero ====== */}
      <section className="relative overflow-hidden bg-gradient-to-br from-indigo-950 via-slate-900 to-slate-950 py-24 sm:py-32">
        {/* Decorative background grid */}
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage:
              "linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
        <div className="relative mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1.5 text-sm text-indigo-300">
            <Brain className="h-4 w-4" aria-hidden="true" />
            Qubettera · Evidence-based AI discussions
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-6xl">
            Multi-Agent{" "}
            <span className="bg-gradient-to-r from-indigo-400 to-teal-400 bg-clip-text text-transparent">
              Opinion Simulator
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            AI personas debate real transformer architecture questions — grounded on a vector knowledge base, analyzed for opinion dynamics, streamed live.
          </p>
          <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link
              href="/discussions"
              id="cta-start-discussion"
              className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-indigo-500/30 transition-all duration-150 hover:bg-indigo-500 hover:shadow-indigo-400/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
            >
              Start a Discussion
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Link>
            <Link
              href="/analytics"
              id="cta-view-analytics"
              className="inline-flex items-center gap-2 rounded-md border border-slate-600 px-6 py-3 text-base font-semibold text-slate-200 transition-all duration-150 hover:border-slate-400 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
            >
              <BarChart2 className="h-5 w-5" aria-hidden="true" />
              View Analytics
            </Link>
          </div>
        </div>
      </section>

      {/* ====== What this is ====== */}
      <section className="py-20 bg-white dark:bg-slate-900">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-8">
            What is this?
          </h2>
          <div className="grid gap-8 sm:grid-cols-3">
            {[
              {
                title: "Multi-Agent Simulation",
                body: "Multiple AI agents, each with a distinct persona, expertise, and stance, participate in a structured debate. They communicate through a strongly-connected directed graph — each agent only reads from its graph predecessors.",
              },
              {
                title: "Opinion Dynamics",
                body: "Over multiple discussion rounds, agent stances evolve as they encounter each other's arguments. The system tracks how opinions shift, which agents drive consensus, and whether the group converges.",
              },
              {
                title: "RAG-Grounded Evidence",
                body: "Live discussions retrieve evidence from your research collection. Source citations accompany responses, and unresolved citation issues are flagged.",
              },
            ].map((item) => (
              <div key={item.title}>
                <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-2">
                  {item.title}
                </h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                  {item.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ====== Pipeline diagram ====== */}
      <section className="py-20 bg-slate-50 dark:bg-slate-950">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-2 text-center">
            5-Week Pipeline
          </h2>
          <p className="text-center text-sm text-slate-500 dark:text-slate-400 mb-12">
            Built incrementally across a 5-week AI engineering fellowship
          </p>
          <div
            className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
            role="list"
            aria-label="Pipeline stages"
          >
            {pipeline.map((stage, i) => {
              const Icon = stage.icon;
              const isLast = i === pipeline.length - 1;
              return (
                <div
                  key={stage.label}
                  className="flex sm:flex-col items-center gap-3 sm:gap-2 flex-1"
                  role="listitem"
                >
                  <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${stage.color} shadow-lg`}>
                    <Icon className="h-6 w-6 text-white" aria-hidden="true" />
                  </div>
                  <div className="sm:text-center">
                    <p className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                      {stage.label}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{stage.sub}</p>
                  </div>
                  {!isLast && (
                    <ArrowRight
                      className="h-5 w-5 text-slate-300 dark:text-slate-600 shrink-0 sm:hidden"
                      aria-hidden="true"
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ====== How it works ====== */}
      <section className="py-20 bg-white dark:bg-slate-900">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-12">
            How it works
          </h2>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <div key={step.title} className="relative">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900 mb-4">
                    <Icon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
                  </div>
                  <span
                    className="absolute top-2 left-10 text-3xl font-black text-slate-100 dark:text-slate-800 select-none -z-0"
                    aria-hidden="true"
                  >
                    {i + 1}
                  </span>
                  <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-2 text-sm relative z-10">
                    {step.title}
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                    {step.body}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ====== Meet the agents ====== */}
      <section className="py-20 bg-slate-50 dark:bg-slate-950" id="agents">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-10">
            <div>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                Meet the Agents
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                {personasUnavailable
                  ? "Personas are temporarily unavailable. Check the backend connection."
                  : `${personas.length} personas with distinct expertise and stances`}
              </p>
            </div>
            <Link
              href="/discussions?tab=personas"
              className="text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 flex items-center gap-1"
            >
              All personas
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {personas.map((persona, i) => {
              const { text, bg } = STANCE_COLORS[i % STANCE_COLORS.length];
              const initials = persona.name
                .split(" ")
                .filter(Boolean)
                .slice(0, 2)
                .map((w) => w[0].toUpperCase())
                .join("");

              return (
                <div
                  key={persona.id}
                  className="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start gap-3 mb-3">
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold ${bg} ${text}`}
                      aria-hidden="true"
                    >
                      {initials}
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-sm text-slate-900 dark:text-slate-100 leading-tight">
                        {persona.name}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        {persona.role}
                      </p>
                    </div>
                  </div>
                  <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium mb-3 ${bg} ${text}`}>
                    {persona.stance}
                  </span>
                  <ul className="space-y-1">
                    {persona.expertise.slice(0, 3).map((tag) => (
                      <li key={tag} className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                        <Check className="h-3 w-3 text-emerald-500 shrink-0" aria-hidden="true" />
                        {tag}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ====== Tech stack ====== */}
      <section className="border-t border-slate-200 dark:border-slate-800 py-12 bg-white dark:bg-slate-900">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500 text-center mb-6">
            Built with
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {[
              "Next.js 16",
              "FastAPI",
              "PostgreSQL + pgvector",
              "LangGraph",
              "Qwen3 retrieval",
              "Recharts",
              "TypeScript",
              "Tailwind CSS v4",
            ].map((tech) => (
              <span
                key={tech}
                className="inline-flex items-center rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
