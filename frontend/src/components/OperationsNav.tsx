import { BookOpenCheck, Database, FlaskConical, KeyRound, PlayCircle } from "lucide-react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/operations", end: true, label: "Pipeline", icon: PlayCircle },
  { to: "/operations/data", end: false, label: "Data", icon: Database },
  { to: "/operations/credentials", end: false, label: "Credentials", icon: KeyRound },
  { to: "/operations/strategies", end: false, label: "Strategies", icon: BookOpenCheck },
  { to: "/operations/research", end: false, label: "Research", icon: FlaskConical },
];

export function OperationsNav() {
  return (
    <nav className="operator-tabs" aria-label="Operator console">
      {links.map(({ to, end, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={end}>
          <Icon aria-hidden="true" size={15} />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
