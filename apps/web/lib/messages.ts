// UI copy catalog. Components import strings from here instead of inlining
// them, so adding a locale later = adding a sibling catalog + a selector.
export const messages = {
  settings: {
    title: "Settings",
    adminSubtitle: "Account, sources, and team — the admin control panel.",
    memberSubtitle: "Your account and preferences.",
    account: "Account",
    logOut: "Log out",
    admin: "Admin",
    workspace: "Workspace",
    managedByAdmin: "Sources and team setup are managed by your workspace admin.",
  },
  sources: {
    heading: "Sources",
    connect: "Connect",
    connected: "Connected",
    slackDesc: "Ingest channel messages",
    dropboxDesc: "Ingest spec PDFs",
    channels: (n: number) => `Connected · ${n} channel${n === 1 ? "" : "s"}`,
    failed: (kind: string) => `Could not start ${kind} connection (is it configured?).`,
  },
  team: {
    heading: "Team",
    hint: "Assign each member their engineering role and the subsystems they own — this is what personalizes their digest.",
    empty: "No members yet. They appear here after their first login.",
    rolePlaceholder: "— role —",
    subsystemsPlaceholder: "subsystems, comma-separated",
    save: "Save",
    saved: "Saved",
  },
} as const;
