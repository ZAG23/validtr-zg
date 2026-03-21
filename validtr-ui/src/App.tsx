import { BrowserRouter, Routes, Route } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { RunDetail } from "@/pages/RunDetail";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="run/:runId" element={<RunDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
