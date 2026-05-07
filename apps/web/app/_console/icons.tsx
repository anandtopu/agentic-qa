/* Lucide-style stroke icons. Match shadcn defaults: 16px, stroke-width 2. */
import type { ReactNode } from "react";

type IconProps = {
  size?: number;
  className?: string;
};

const Icon = ({ children, size = 16, className = "" }: IconProps & { children: ReactNode }): JSX.Element => (
  <svg
    className={"icon " + className}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    {children}
  </svg>
);

export type IconCmp = (p: IconProps) => JSX.Element;

export const Icons = {
  Gauge: (p) => (
    <Icon {...p}>
      <path d="m12 14 4-4" />
      <path d="M3.34 19a10 10 0 1 1 17.32 0" />
    </Icon>
  ),
  Activity: (p) => (
    <Icon {...p}>
      <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.5.5 0 0 1-.96 0L9.24 2.18a.5.5 0 0 0-.96 0l-2.35 8.36A2 2 0 0 1 4 12H2" />
    </Icon>
  ),
  Bug: (p) => (
    <Icon {...p}>
      <path d="m8 2 1.88 1.88" />
      <path d="M14.12 3.88 16 2" />
      <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1" />
      <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6" />
      <path d="M12 20v-9" />
      <path d="M6.53 9C4.6 8.8 3 7.1 3 5" />
      <path d="M6 13H2" />
      <path d="M3 21c0-2.1 1.7-3.9 3.8-4" />
      <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4" />
      <path d="M22 13h-4" />
      <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4" />
    </Icon>
  ),
  ShieldCheck: (p) => (
    <Icon {...p}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </Icon>
  ),
  FileText: (p) => (
    <Icon {...p}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M10 9H8" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
    </Icon>
  ),
  Beaker: (p) => (
    <Icon {...p}>
      <path d="M4.5 3h15" />
      <path d="M6 3v16a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V3" />
      <path d="M6 14h12" />
    </Icon>
  ),
  ScrollText: (p) => (
    <Icon {...p}>
      <path d="M15 12h-5" />
      <path d="M15 8h-5" />
      <path d="M19 17V5a2 2 0 0 0-2-2H4" />
      <path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" />
    </Icon>
  ),
  ClipboardCheck: (p) => (
    <Icon {...p}>
      <rect width={8} height={4} x={8} y={2} rx={1} ry={1} />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <path d="m9 14 2 2 4-4" />
    </Icon>
  ),
  Search: (p) => (
    <Icon {...p}>
      <circle cx={11} cy={11} r={8} />
      <path d="m21 21-4.3-4.3" />
    </Icon>
  ),
  Settings: (p) => (
    <Icon {...p}>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2" />
      <circle cx={12} cy={12} r={3} />
    </Icon>
  ),
  Chevron: (p) => (
    <Icon {...p}>
      <path d="m9 18 6-6-6-6" />
    </Icon>
  ),
  ChevronDown: (p) => (
    <Icon {...p}>
      <path d="m6 9 6 6 6-6" />
    </Icon>
  ),
  Play: (p) => (
    <Icon {...p}>
      <polygon points="6 3 20 12 6 21 6 3" />
    </Icon>
  ),
  Pause: (p) => (
    <Icon {...p}>
      <rect x={14} y={3} width={5} height={18} rx={1} />
      <rect x={5} y={3} width={5} height={18} rx={1} />
    </Icon>
  ),
  RefreshCw: (p) => (
    <Icon {...p}>
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M3 21v-5h5" />
    </Icon>
  ),
  Plus: (p) => (
    <Icon {...p}>
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </Icon>
  ),
  GitPullRequest: (p) => (
    <Icon {...p}>
      <circle cx={18} cy={18} r={3} />
      <circle cx={6} cy={6} r={3} />
      <path d="M13 6h3a2 2 0 0 1 2 2v7" />
      <path d="M6 9v12" />
    </Icon>
  ),
  ArrowRight: (p) => (
    <Icon {...p}>
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </Icon>
  ),
  Eye: (p) => (
    <Icon {...p}>
      <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" />
      <circle cx={12} cy={12} r={3} />
    </Icon>
  ),
  Code: (p) => (
    <Icon {...p}>
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </Icon>
  ),
  Globe: (p) => (
    <Icon {...p}>
      <circle cx={12} cy={12} r={10} />
      <path d="M12 2a14.5 14.5 0 0 0 0 20" />
      <path d="M12 2a14.5 14.5 0 0 1 0 20" />
      <path d="M2 12h20" />
    </Icon>
  ),
  Database: (p) => (
    <Icon {...p}>
      <ellipse cx={12} cy={5} rx={9} ry={3} />
      <path d="M3 5v14a9 3 0 0 0 18 0V5" />
      <path d="M3 12a9 3 0 0 0 18 0" />
    </Icon>
  ),
  Zap: (p) => (
    <Icon {...p}>
      <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />
    </Icon>
  ),
} satisfies Record<string, IconCmp>;

export type IconName = keyof typeof Icons;

export function getIcon(name: string): IconCmp | undefined {
  return (Icons as Record<string, IconCmp>)[name];
}

