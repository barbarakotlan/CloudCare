import type { Metadata } from "next";
import { PatientDashboardRoute } from "@/components/patient/PatientDashboard";

export const metadata: Metadata = {
  title: "My recovery",
  robots: { index: false },
};

export default function PatientDashboardPage() {
  return <PatientDashboardRoute />;
}
