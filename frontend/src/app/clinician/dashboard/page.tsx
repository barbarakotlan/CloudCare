import type { Metadata } from "next";
import { ClinicianDashboardRoute } from "@/components/clinician/ClinicianDashboard";

export const metadata: Metadata = {
  title: "Care team",
  robots: { index: false },
};

export default function ClinicianDashboardPage() {
  return <ClinicianDashboardRoute />;
}
