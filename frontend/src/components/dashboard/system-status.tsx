"use client";

import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function SystemStatus() {
  const { data, isPending, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
  });

  const ok = !isPending && !isError && data?.status === "ok";

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle className="text-text-strong">System status</CardTitle>
        <CardDescription>Backend API health</CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-4">
        {isPending ? (
          <Badge variant="outline" className="text-text-muted">
            Checking...
          </Badge>
        ) : ok ? (
          <Badge className="bg-fin-success-bg text-fin-success-dark">OK</Badge>
        ) : (
          <Badge className="bg-fin-danger-bg text-fin-danger">
            {isError ? error.message : "Unhealthy"}
          </Badge>
        )}
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="rounded text-sm font-medium text-bank-accent hover:underline disabled:opacity-50"
        >
          Refresh
        </button>
      </CardContent>
    </Card>
  );
}
