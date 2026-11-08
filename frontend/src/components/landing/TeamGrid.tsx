import { ArrowUpRight } from "lucide-react";
import { TeamPhoto } from "./TeamPhoto";

export type TeamMember = {
  name: string;
  role: string;
  /** File in public/team/ (transparent-background PNG, roughly square, head and shoulders). */
  photo: string;
  blurb: string;
  linkedin: string;
};

export const TEAM: TeamMember[] = [
  {
    name: "Jacob Foti",
    role: "Co-founder",
    photo: "jacob.png",
    blurb:
      "Business lead. Has helped run a company with over $50M in annual recurring revenue, and keeps CloudCare focused on what patients and anesthesia teams will actually use.",
    linkedin: "https://www.linkedin.com/in/jacobfoti/",
  },
  {
    name: "Barbara Kotlan",
    role: "Co-founder",
    photo: "barbara.png",
    blurb:
      "Backend and data. RPI student with a job offer from Epic, building the FastAPI service, schema and clinician workflows.",
    linkedin: "https://www.linkedin.com/in/barbara-kotlan/",
  },
  {
    name: "Anna Kotlan",
    role: "Co-founder",
    photo: "anna.png",
    blurb:
      "AI and ML. Data engineer at Fidelity with an MBA in data analytics and a strong hackathon record; builds Foggy's grounding, the risk model and the Epic integration.",
    linkedin: "https://www.linkedin.com/in/annakotlan/",
  },
];

function TeamCard({ member }: { member: TeamMember }) {
  return (
    <li className="flex flex-col items-center rounded-[2rem] bg-white p-6 text-center shadow-soft ring-1 ring-line/70 sm:p-8">
      <TeamPhoto src={`/team/${member.photo}`} name={member.name} />
      <h2 className="mt-5 text-xl font-black tracking-tight text-ink">{member.name}</h2>
      <p className="mt-1 text-sm font-extrabold tracking-[0.12em] text-brand-cyan-strong uppercase">{member.role}</p>
      <p className="mt-4 flex-1 leading-relaxed text-pretty text-ink-soft">{member.blurb}</p>
      <a
        href={member.linkedin}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-bold text-brand-cyan-strong hover:underline focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan"
      >
        LinkedIn
        <ArrowUpRight className="size-4" aria-hidden="true" />
        <span className="sr-only">: {member.name} (opens in a new tab)</span>
      </a>
    </li>
  );
}

export function TeamGrid() {
  return (
    <ul className="mx-auto grid max-w-md grid-cols-1 gap-5 sm:gap-6 lg:max-w-none lg:grid-cols-3" aria-label="Co-founders">
      {TEAM.map((member) => (
        <TeamCard key={member.name} member={member} />
      ))}
    </ul>
  );
}
