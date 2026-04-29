export default function HomePage(): JSX.Element {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">QAForge AI</h1>
      <p className="text-lg text-slate-600 dark:text-slate-300">
        Agentic software QA platform — dashboard skeleton (Phase 0).
      </p>
      <p className="text-sm text-slate-500">
        First real surfaces arrive in Phase 1: workspace setup, plan review (Story 1.3.3),
        approvals queue, and run evidence.
      </p>
    </main>
  );
}
