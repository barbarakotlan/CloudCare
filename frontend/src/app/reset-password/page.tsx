import type { Metadata } from "next";
import Link from "next/link";
import { BrandLockup } from "@/components/brand/CloudMark";
import { ResetPasswordForm } from "@/components/app/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Choose a new password",
  description: "Set a new CloudCare password from your reset link.",
};

export default function ResetPasswordPage() {
  return (
    <main id="main" className="flex min-h-dvh flex-1 flex-col bg-surface-soft px-4 py-6 sm:px-8 sm:py-10">
      <Link href="/" className="inline-flex min-h-11 items-center self-start rounded-xl" aria-label="CloudCare home">
        <BrandLockup size={40} />
      </Link>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
        <h1 className="text-3xl font-black tracking-tight text-ink sm:text-4xl">Choose a new password</h1>
        <ResetPasswordForm />
      </div>
    </main>
  );
}
