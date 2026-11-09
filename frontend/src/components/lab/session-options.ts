import type { Option } from "@/components/shared/form-layout";

export const KIND_OPTS: Option<"practice" | "exam">[] = [
  { value: "practice", label: "Practice", hint: "Open-ended class practice." },
  { value: "exam", label: "Exam", hint: "Single bank, own work only." },
];
export const STRUCTURE_OPTS: Option<"single_bank" | "per_group">[] = [
  { value: "single_bank", label: "Single bank", hint: "One bank shared by all." },
  { value: "per_group", label: "One bank per group", hint: "Each group runs its own bank." },
];
export const VIS_OPTS: Option<"all" | "own">[] = [
  { value: "all", label: "Whole bank", hint: "Members see all bank work." },
  { value: "own", label: "Own work only", hint: "Members see only their work." },
];

