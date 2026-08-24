import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { DeskPage } from "./pages/DeskPage";
import { CredentialsPage } from "./pages/CredentialsPage";
import { DataManagementPage } from "./pages/DataManagementPage";
import { FactorSignificancePage } from "./pages/FactorSignificancePage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { OperationsOverviewPage } from "./pages/OperationsOverviewPage";
import { StrategyDetailPage } from "./pages/StrategyDetailPage";
import { StrategyRegistryPage } from "./pages/StrategyRegistryPage";
import { SymbolDirectoryPage } from "./pages/SymbolDirectoryPage";
import { SymbolPage } from "./pages/SymbolPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DeskPage />} />
        <Route path="symbols" element={<SymbolDirectoryPage />} />
        <Route path="symbols/:symbol" element={<SymbolPage />} />
        <Route path="operations" element={<OperationsOverviewPage />} />
        <Route path="operations/data" element={<DataManagementPage />} />
        <Route path="operations/credentials" element={<CredentialsPage />} />
        <Route path="operations/strategies" element={<StrategyRegistryPage />} />
        <Route path="operations/strategies/:key" element={<StrategyDetailPage />} />
        <Route path="operations/research" element={<FactorSignificancePage />} />
        <Route path="operations/methodology" element={<MethodologyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
