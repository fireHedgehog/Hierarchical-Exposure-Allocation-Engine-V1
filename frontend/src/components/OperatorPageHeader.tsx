import type { ReactNode } from "react";
import { OperationsNav } from "./OperationsNav";

export function OperatorPageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <>
      <header className="workspace-header operator-workspace-header">
        <div>
          <p className="eyebrow">Local operator console</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {action}
      </header>
      <OperationsNav />
    </>
  );
}
