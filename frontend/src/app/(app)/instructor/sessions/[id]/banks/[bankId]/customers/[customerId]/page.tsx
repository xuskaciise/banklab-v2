"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/lab/common";
import { CustomerDetailView } from "@/components/customers/customer-detail";

export default function StaffCustomerPage() {
  const { id, bankId, customerId } = useParams<{
    id: string;
    bankId: string;
    customerId: string;
  }>();
  return (
    <div className="space-y-6">
      <PageHeader
        title="Customer"
        subtitle="Read-only view"
        actions={
          <Link
            href={`/instructor/sessions/${id}`}
            className={buttonVariants({ variant: "outline" })}
          >
            <ArrowLeft /> Session
          </Link>
        }
      />
      <CustomerDetailView
        scope={{ kind: "staff", sessionId: id, bankId }}
        id={customerId}
        canEdit={false}
      />
    </div>
  );
}
