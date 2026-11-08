import Link from "next/link";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "danger-ghost" | "soft" | "link";
export type ButtonSize = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 rounded-full font-bold whitespace-nowrap transition-[background-color,color,box-shadow,transform] duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-55 focus-visible:outline-offset-[3px]";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-cyan text-white shadow-[0_6px_16px_-6px_rgb(25_154_192/0.55)] hover:bg-brand-cyan-strong",
  secondary:
    "bg-white text-brand-cyan-strong ring-1 ring-inset ring-line hover:ring-brand-cyan hover:bg-surface-soft",
  ghost: "text-ink-soft hover:bg-surface-pale hover:text-ink",
  danger: "bg-brand-red text-white hover:bg-brand-red-dark",
  "danger-ghost": "text-brand-red-dark ring-1 ring-inset ring-brand-red/25 hover:bg-brand-red/8",
  soft: "bg-surface-pale text-brand-cyan-strong hover:bg-[#d3edf4]",
  // Inline text action (cn() concatenates, so text color has to come from the variant, not className).
  link: "text-brand-cyan-strong underline-offset-4 hover:bg-surface-pale hover:text-brand-cyan hover:underline",
};

const sizes: Record<ButtonSize, string> = {
  // 40 px tall on phones (touch target), 36 px from sm up.
  sm: "h-10 px-4 text-sm sm:h-9",
  md: "h-11 px-5 text-[0.95rem]",
  lg: "h-14 px-7 text-[1.05rem]",
};

export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", className?: string) {
  return cn(base, variants[variant], sizes[size], className);
}

type ButtonProps = ComponentProps<"button"> & { variant?: ButtonVariant; size?: ButtonSize };

export function Button({ variant = "primary", size = "md", className, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={buttonClasses(variant, size, className)} {...props} />;
}

type ButtonLinkProps = ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: ButtonSize };

export function ButtonLink({ variant = "primary", size = "md", className, ...props }: ButtonLinkProps) {
  return <Link className={buttonClasses(variant, size, className)} {...props} />;
}
