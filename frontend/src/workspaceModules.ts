export const workspaceModules = {
  crossSectionalRanking: { enabled: true, path: "/cross-sectional-ranking", label: "Cross-sectional ranking" },
  timing: { enabled: true, path: "/symbols", label: "Timing" },
} as const;

export function workspaceModuleEnabled(key: keyof typeof workspaceModules) {
  return workspaceModules[key].enabled;
}
