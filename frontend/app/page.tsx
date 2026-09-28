import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-between flex-col space-y-8 font-mono text-sm flex">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">
          COVENANT Platform
        </h1>
        <p className="text-lg text-slate-600 text-center max-w-2xl">
          AI Contract & Invoice Risk Intelligence. Detect deviations, evaluate risk, and generate actionable redlines.
        </p>
        <div className="flex gap-4">
          <Button size="lg">Upload Document</Button>
          <Button size="lg" variant="outline">View Dashboard</Button>
        </div>
      </div>
    </main>
  );
}